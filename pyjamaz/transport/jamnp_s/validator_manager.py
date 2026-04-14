from __future__ import annotations

import logging
import math
import time
from base64 import b32encode
from dataclasses import dataclass
from enum import IntEnum
from typing import Awaitable, Callable, Dict, Iterable, Optional, TYPE_CHECKING

from aioquic.quic.connection import QuicConnectionState

from pyjamaz import settings

logger = logging.getLogger("pyjamaz.transport.jamnp_s")

if TYPE_CHECKING:
    from pyjamaz.app import PyjamazApp
    from pyjamaz.models.common import ValidatorData
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
    desired_since: Optional[float] = None
    initiator: bool = False
    in_grid: bool = False


class ValidatorConnectionManager:
    FALLBACK_INITIATOR_TIMEOUT = 5.0
    RETRY_INTERVAL = 3.0

    def __init__(
        self,
        app: "PyjamazApp",
        connect_callback: ConnectCallback,
        disconnect_callback: DisconnectCallback,
        port_override: Optional[int] = None,
    ) -> None:
        self.app = app
        self.connect_callback = connect_callback
        self.disconnect_callback = disconnect_callback
        self.port_override = port_override
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

        for validator in self._validator_sets():
            if validator.ed25519 == self.app.config.keys.ed25519.public_key:
                self.validator = validator
                self.validator_address, self.validator_port = self.get_validator_endpoint(validator)
                peer_id = b32encode(validator.ed25519).decode("ascii").lower().rstrip("=")
                self.validator_dns = f"e{peer_id}@{self.validator_address}:{self.validator_port}"
                return


    def _validator_sets(self) -> Iterable[ValidatorData]:
        yield from self.app.working_state.validator_queue.validators
        yield from self.app.working_state.validator_pool.validators
        yield from self.app.working_state.validator_archive.validators


    @staticmethod
    def should_initiate_connection(validator_a: bytes, validator_b: bytes) -> bool:
        connect_a = 1 if validator_a[31] > 127 else 0
        connect_b = 1 if validator_b[31] > 127 else 0
        a_less = 1 if validator_a < validator_b else 0
        return (connect_a ^ connect_b ^ a_less) == 1


    def _debug_validator_override(self, validator: "ValidatorData") -> Optional[tuple[str, int]]:
        overrides = getattr(settings, "VALIDATOR_ENDPOINT_OVERRIDES", {}) or {}
        value = overrides.get(f"0x{validator.ed25519.hex()}")
        if value is None:
            value = overrides.get(validator.ed25519.hex())

        if isinstance(value, str):
            host, sep, port_str = value.rpartition(":")
            if not sep:
                raise ValueError(f"Invalid validator endpoint override: {value!r}")
            return host, int(port_str)

        if isinstance(value, (tuple, list)) and len(value) == 2:
            host, port = value
            return str(host), int(port)

        if value is None:
            return None

        raise ValueError(f"Unsupported validator endpoint override: {value!r}")


    def get_validator_endpoint(self, validator: ValidatorData) -> tuple[str, int]:
        override = self._debug_validator_override(validator)
        if override is not None:
            return override

        ip = validator.get_metadata_ipaddress()
        port = validator.get_metadata_port()
        if self.port_override is not None and self.validator is not None:
            port_delta = self.port_override - self.validator.get_metadata_port()
            port += port_delta
        return ip, port


    def get_neighbors(
        self,
        validator_set: list[ValidatorData],
        local_key: bytes,
        other_sets: Iterable[list[ValidatorData]],
    ) -> Dict[bytes, ValidatorData]:
        local_index = next(
            (index for index, validator in enumerate(validator_set) if validator.ed25519 == local_key),
            None,
        )
        if local_index is None:
            return {}

        neighbors: Dict[bytes, ValidatorData] = {}
        width = max(1, math.floor(math.sqrt(len(validator_set))))
        local_row = local_index // width
        local_column = local_index % width

        for index, validator in enumerate(validator_set):
            if (index // width) == local_row or (index % width) == local_column:
                neighbors[validator.ed25519] = validator

        for other_set in other_sets:
            if local_index < len(other_set):
                validator = other_set[local_index]
                neighbors[validator.ed25519] = validator

        neighbors.pop(local_key, None)
        return neighbors


    def build_grid_neighbors(self) -> Dict[bytes, ValidatorData]:
        if self.validator is None:
            return {}

        prev_validators = self.app.working_state.validator_archive.validators
        current_validators = self.app.working_state.validator_pool.validators
        next_validators = self.app.working_state.validator_queue.validators

        neighbors: Dict[bytes, ValidatorData] = {}
        local_key = self.validator.ed25519

        for validator in self.get_neighbors(prev_validators, local_key, [current_validators, next_validators]).values():
            neighbors[validator.ed25519] = validator
        for validator in self.get_neighbors(current_validators, local_key, []).values():
            neighbors[validator.ed25519] = validator
        for validator in self.get_neighbors(next_validators, local_key, []).values():
            neighbors[validator.ed25519] = validator

        return neighbors


    @staticmethod
    def is_connection_active(connection: Optional["JAMConnection"]) -> bool:
        if connection is None:
            return False

        quic = getattr(connection, "_quic", None)
        if quic is None:
            return False

        if getattr(quic, "_close_pending", False):
            return False

        state = getattr(quic, "_state", None)
        if state is None:
            return False

        terminal_states = {
            QuicConnectionState.CLOSING,
            QuicConnectionState.DRAINING,
            QuicConnectionState.TERMINATED,
        }
        return state not in terminal_states


    def has_tracked_validator(self, validator_key: bytes) -> bool:
        return validator_key in self.connections


    async def update_validator_connections(self) -> None:
        self.refresh_local_validator()

        if not self.validator:
            return

        now = time.time()
        new_neighbors = self.build_grid_neighbors()
        new_keys = set(new_neighbors)
        current_keys = set(self.connections)

        for ed25519 in current_keys - new_keys:
            state = self.connections.pop(ed25519, None)
            if state and state.connection is not None:
                self.disconnect_callback(state.connection, ed25519)

        for ed25519 in new_keys:
            validator = new_neighbors[ed25519]
            is_initiator = self.should_initiate_connection(self.validator.ed25519, validator.ed25519)
            in_grid = True
            ip, port = self.get_validator_endpoint(validator)

            state = self.connections.get(ed25519)
            if state is None:
                state = ValidatorConnection(
                    validator=validator,
                    ip=ip,
                    port=port,
                    initiator=is_initiator,
                    in_grid=in_grid,
                    desired_since=now,
                )
                self.connections[ed25519] = state
            else:
                state.validator = validator
                state.ip = ip
                state.port = port
                state.initiator = is_initiator
                state.in_grid = in_grid
                if state.desired_since is None:
                    state.desired_since = now

            if self.is_connection_active(state.connection):
                continue

            state.connection = None

            if state.last_try is not None and (now - state.last_try) < self.RETRY_INTERVAL:
                continue

            should_attempt = state.initiator
            if (
                not should_attempt
                and state.desired_since is not None
                and (now - state.desired_since) >= self.FALLBACK_INITIATOR_TIMEOUT
            ):
                should_attempt = True

            if not should_attempt:
                continue

            state.last_try = now
            await self.connect_callback(state.ip, state.port, ed25519)


    def bind_connection(self, validator_key: bytes, connection: "JAMConnection") -> None:
        connection.validator_key = validator_key
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
