from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Optional, TYPE_CHECKING

from aioquic.quic.connection import QuicConnectionState

from pyjamaz.models.common import ValidatorData

logger = logging.getLogger("pyjamaz.transport.jamnp_s")

if TYPE_CHECKING:
    from pyjamaz.app import PyjamazApp
    from pyjamaz.transport.jamnp_s.connection import JAMConnection

ConnectCallback = Callable[[str, int, Optional[bytes]], Awaitable[None]]
DisconnectCallback = Callable[["JAMConnection", Optional[bytes]], None]


@dataclass
class ValidatorConnection:
    validator: ValidatorData
    ip: str
    port: int
    connection: Optional["JAMConnection"] = None
    last_try: Optional[float] = None
    initiator: bool = False
    in_grid: bool = False


class ValidatorConnectionManager:
    def __init__(
        self,
        app: "PyjamazApp",
        connect_callback: ConnectCallback,
        disconnect_callback: DisconnectCallback,
    ) -> None:
        self.app = app
        self.connect_callback = connect_callback
        self.disconnect_callback = disconnect_callback
        self.connections: Dict[bytes, ValidatorConnection] = {}

        self.validator = None
        self.validator_dns = None
        self.validator_port = None
        self.validator_address = None
        self.refresh_local_validator()

    def refresh_local_validator(self) -> None:
        self.validator = None
        self.validator_dns = None
        self.validator_port = None
        self.validator_address = None

        if self.app.config.keys is None:
            return

        for validator in self.app.working_state.safrole.validators:
            if validator.ed25519 == self.app.config.keys.ed25519.public_key:
                self.validator = validator
                self.validator_dns = validator.get_connection_dns()
                self.validator_port = validator.get_metadata_port()
                self.validator_address = validator.get_metadata_ipaddress()
                return

    @staticmethod
    def should_initiate_connection(validator_a: bytes, validator_b: bytes) -> bool:
        connect_a = 1 if validator_a[31] > 127 else 0
        connect_b = 1 if validator_b[31] > 127 else 0
        a_less = 1 if validator_a < validator_b else 0
        return (connect_a ^ connect_b ^ a_less) == 1

    def _add_grid_connections(
        self,
        validator_idx: int,
        validator_queue,
        same_epoch: bool,
        initiate_conns: Dict[bytes, ValidatorData],
        expect_conns: Dict[bytes, ValidatorData],
    ) -> None:
        width = max(1, math.floor(math.sqrt(len(validator_queue))))

        for v_idx, validator in validator_queue:
            if self.validator.ed25519 == validator.ed25519:
                continue

            should_connect = False
            if same_epoch:
                same_row = (v_idx // width) == (validator_idx // width)
                same_column = (validator_idx % width) == (v_idx % width)
                should_connect = same_row or same_column
            else:
                should_connect = v_idx == validator_idx

            if not should_connect:
                continue

            if self.should_initiate_connection(self.validator.ed25519, validator.ed25519):
                initiate_conns[validator.ed25519] = validator
            else:
                expect_conns[validator.ed25519] = validator

    async def update_connections(self) -> None:
        self.refresh_local_validator()

        if not self.validator:
            raise Exception("This node is not a validator")

        prev_validators = list(enumerate(self.app.working_state.validator_archive.validators))
        next_validators = list(enumerate(self.app.working_state.validator_queue.validators))
        active_validators = list(enumerate(self.app.working_state.safrole.validators))

        validator_idx = None
        for v_idx, validator in active_validators:
            if validator.ed25519 == self.validator.ed25519:
                validator_idx = v_idx
                break

        if validator_idx is None:
            logger.debug(
                f"Current validator {self.validator.ed25519.hex()} is not present in the validator queue"
            )
            return

        initiate_grid_connections: Dict[bytes, ValidatorData] = {}
        expected_grid_connections: Dict[bytes, ValidatorData] = {}
        self._add_grid_connections(
            validator_idx,
            prev_validators,
            same_epoch=False,
            initiate_conns=initiate_grid_connections,
            expect_conns=expected_grid_connections,
        )
        self._add_grid_connections(
            validator_idx,
            active_validators,
            same_epoch=True,
            initiate_conns=initiate_grid_connections,
            expect_conns=expected_grid_connections,
        )
        self._add_grid_connections(
            validator_idx,
            next_validators,
            same_epoch=False,
            initiate_conns=initiate_grid_connections,
            expect_conns=expected_grid_connections,
        )

        initiate_connections: Dict[bytes, ValidatorData] = {}
        expected_connections: Dict[bytes, ValidatorData] = {}
        for _, validator in active_validators:
            if validator.ed25519 == self.validator.ed25519:
                continue

            if self.should_initiate_connection(self.validator.ed25519, validator.ed25519):
                initiate_connections[validator.ed25519] = validator
            else:
                expected_connections[validator.ed25519] = validator

        new_keys = (
            set(initiate_connections)
            | set(expected_connections)
            | set(initiate_grid_connections)
            | set(expected_grid_connections)
        )
        current_keys = set(self.connections)

        for ed25519 in current_keys - new_keys:
            state = self.connections.pop(ed25519, None)
            if state and state.connection is not None:
                self.disconnect_callback(state.connection, ed25519)

        for ed25519 in new_keys:
            validator = (
                initiate_connections.get(ed25519)
                or expected_connections.get(ed25519)
                or initiate_grid_connections.get(ed25519)
                or expected_grid_connections.get(ed25519)
            )
            if validator is None:
                continue

            is_initiator = ed25519 in initiate_connections or ed25519 in initiate_grid_connections
            in_grid = ed25519 in initiate_grid_connections or ed25519 in expected_grid_connections

            state = self.connections.get(ed25519)
            if state is None:
                state = ValidatorConnection(
                    validator=validator,
                    ip=validator.get_metadata_ipaddress(),
                    port=validator.get_metadata_port(),
                    initiator=is_initiator,
                    in_grid=in_grid,
                )
                self.connections[ed25519] = state
            else:
                state.validator = validator
                state.ip = validator.get_metadata_ipaddress()
                state.port = validator.get_metadata_port()
                state.initiator = is_initiator
                state.in_grid = in_grid

            if not (state.in_grid and state.initiator):
                continue

            if state.connection is None or state.connection._quic._state > QuicConnectionState.CONNECTED:
                await self.connect_callback(state.ip, state.port, ed25519)

    def bind_connection(self, validator_key: bytes, connection: "JAMConnection") -> None:
        state = self.connections.get(validator_key)
        if state is None:
            return

        if state.connection is not None and state.connection is not connection:
            self.disconnect_callback(state.connection, validator_key)

        state.connection = connection
        state.last_try = time.time()

    def on_disconnect(self, connection: "JAMConnection", validator_key: Optional[bytes] = None) -> None:
        validator_key = validator_key or getattr(connection, "validator_key", None)
        if validator_key is None:
            return

        state = self.connections.get(validator_key)
        if state is None:
            return

        if state.connection is connection:
            state.connection = None
