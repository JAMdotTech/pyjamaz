"""Telemetry protocol implementation following JIP-3."""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import time
from contextlib import suppress
from typing import Dict, Iterable, List, Optional

import pyjamaz.graypaper_constants as gp_const
from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.models.block import Block
from pyjamaz.settings import APP_VERSION, GP_VERSION
from pyjamaz.transport.pubsub import PubSubSignal
from pyjamaz.transport.types import ProtocolType

from .connection import TelemetryConnection, TelemetryConnectionError
from .message_types import (
    TelemetryAccumulateCost,
    TelemetryBlockAuthoredEvent,
    TelemetryBlockAuthoringEvent,
    TelemetryBlockExecutedEvent,
    TelemetryBlockImportingEvent,
    TelemetryBlockOutline,
    TelemetryBlockVerificationFailedEvent,
    TelemetryBlockVerifiedEvent,
    TelemetryExecCost,
    TelemetryJamParameters,
    TelemetryJamParametersV1,
    TelemetryNodeInfo,
    TelemetryPeerAddress,
    TelemetryServiceCost,
    TelemetryStatusEvent,
)

logger = logging.getLogger("pyjamaz.transport.telemetry")


class TelemetryClient(ProtocolType):
    """Telemetry client"""

    MAX_SERVICE_COST_ENTRIES = 500

    def __init__(
        self,
        app,
        host: str,
        port: int,
        *,
        node_flags: int = 0,
        implementation_name: str = "Pyjamaz",
        implementation_version: str = APP_VERSION,
        graypaper_version: str = GP_VERSION,
        note: str = "",
        local_address: Optional[str] = None,
        local_port: Optional[int] = None,
        status_interval: float = 2.0,
        reconnect_delay: float = 5.0,
    ) -> None:
        self.app = app
        self._connection: Optional[TelemetryConnection] = None
        self._host = host
        self._port = port
        self._status_interval = status_interval
        self._reconnect_delay = reconnect_delay
        self._node_flags = node_flags
        self._implementation_name = implementation_name
        self._implementation_version = implementation_version
        self._graypaper_version = graypaper_version
        self._note = note
        self._local_address = local_address
        self._local_port = local_port

        self._send_lock = asyncio.Lock()
        self._next_event_id = 0
        self._authoring_event_ids: Dict[int, int] = {}
        self._block_event_ids: Dict[bytes, int] = {}

        self._status_task: Optional[asyncio.Task] = None
        self._running = False
        self._connection_lost = asyncio.Event()

        self._pubsub_registered = False
        if self.app.pubsub:
            self._register_pubsub()


    async def listen(self) -> None:
        self.register_pubsub_handlers()
        if self._status_task is None:
            self._status_task = asyncio.create_task(self._status_loop())

        self._running = True
        try:
            while self._running:
                try:
                    await self._connect()
                    await self._send_node_info()
                    await self._send_status_event()
                    # Wait until connection is lost or stop requested
                    await self._connection_lost.wait()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # pragma: no cover - defensive
                    logger.exception("Telemetry client error: %s", exc)
                finally:
                    await self._cleanup_connection()
                if not self._running:
                    break
                await asyncio.sleep(self._reconnect_delay)
        finally:
            if self._status_task:
                self._status_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._status_task
                self._status_task = None


    def _register_pubsub(self) -> None:
        self.app.pubsub.subscribe(MESSAGE_TYPES.BLOCK_AUTHORING, self._handle_block_authoring)
        self.app.pubsub.subscribe(MESSAGE_TYPES.BLOCK_AUTHORED, self._handle_block_authored)
        self.app.pubsub.subscribe(MESSAGE_TYPES.BLOCK_IMPORTING, self._handle_block_importing)
        self.app.pubsub.subscribe(MESSAGE_TYPES.BLOCK_VERIFIED, self._handle_block_verified)
        self.app.pubsub.subscribe(MESSAGE_TYPES.BLOCK_VERIFICATION_FAILED, self._handle_block_verification_failed)
        self.app.pubsub.subscribe(MESSAGE_TYPES.BLOCK_EXECUTED, self._handle_block_executed)
        self._pubsub_registered = True


    def register_pubsub_handlers(self) -> None:
        if not self._pubsub_registered and self.app.pubsub:
            self._register_pubsub()


    async def _connect(self) -> None:
        await self._cleanup_connection()
        self._connection = TelemetryConnection(self._host, self._port)
        await self._connection.connect()
        self._next_event_id = 0
        self._authoring_event_ids.clear()
        self._block_event_ids.clear()
        self._connection_lost.clear()


    async def _cleanup_connection(self) -> None:
        if self._connection:
            await self._connection.close()
        self._connection = None


    async def _send_node_info(self) -> None:
        params = self.create_parameters()
        genesis_hash = self.app.retrieve_block_hash(0) or bytes(32)
        peer_id = getattr(getattr(self.app.config, "keys", None), "ed25519", None)
        peer_id_bytes = peer_id.public_key if peer_id else bytes(32)
        node_info = TelemetryNodeInfo(
            parameters=params,
            genesis_hash=genesis_hash,
            peer_id=peer_id_bytes,
            peer_address=self.create_peer_address(),
            node_flags=self._node_flags,
            implementation_name=self._implementation_name,
            implementation_version=self._implementation_version,
            graypaper_version=self._graypaper_version,
            note=self._note,
        )
        await self._send_raw(node_info)


    async def _status_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._status_interval)
                await self._send_status_event()
        except asyncio.CancelledError:
            pass


    async def _send_status_event(self) -> None:
        if not self._connection or not self._connection.is_connected():
            return

        (
            total_peers,
            validator_peers,
            block_announcement_peers,
            guarantees_by_core,
            availability_shards,
            availability_shards_size,
            preimages_ready,
            preimages_ready_size,
        ) = self.collect_stats()

        event = TelemetryStatusEvent(
            timestamp=self._timestamp(),
            total_peers=total_peers,
            validator_peers=validator_peers,
            block_announcement_peers=block_announcement_peers,
            guarantees_by_core=guarantees_by_core,
            availability_shards=availability_shards,
            availability_shards_size=availability_shards_size,
            preimages_ready=preimages_ready,
            preimages_ready_size=preimages_ready_size,
        )
        await self._send_event(event)


    def collect_stats(self):
        protocol = getattr(self.app, "protocol", None)
        connections = getattr(protocol, "connections", {}) if protocol else {}
        total_peers = len(connections)
        validator_peers = total_peers
        block_announcement_peers = 0

        guarantees_by_core = [0] * gp_const.CORE_COUNT

        availability_shards = 0
        availability_shards_size = 0

        preimage_queue = getattr(self.app.block_extrinsic, "preimage_queue", [])
        preimages_ready = len(preimage_queue)
        preimages_ready_size = sum(len(preimage.blob) for preimage in preimage_queue)

        return (
            total_peers,
            validator_peers,
            block_announcement_peers,
            guarantees_by_core,
            availability_shards,
            availability_shards_size,
            preimages_ready,
            preimages_ready_size,
        )


    async def _handle_block_authoring(self, payload) -> None:
        if not isinstance(payload, dict):
            return
        slot = payload.get("slot")
        parent_hash = payload.get("parent_hash")
        if not isinstance(slot, int) or not isinstance(parent_hash, bytes) or len(parent_hash) != 32:
            logger.debug("Telemetry block authoring received unexpected payload: %r", payload)
            return

        event = TelemetryBlockAuthoringEvent(
            timestamp=self._timestamp(),
            slot=slot,
            parent_hash=parent_hash,
        )
        event_id = await self._send_event(event)
        if event_id is not None:
            self._authoring_event_ids[slot] = event_id


    async def _handle_block_authored(self, payload) -> None:
        block = self._resolve_block(payload)
        if block is None:
            return

        authoring_event_id = self._authoring_event_ids.pop(block.header.timeslot, None)
        if authoring_event_id is None:
            logger.debug("Telemetry skip block authored: no authoring event id")
            return

        event = TelemetryBlockAuthoredEvent(
            timestamp=self._timestamp(),
            authoring_event_id=authoring_event_id,
            outline=self._build_block_outline(block),
        )
        event_id = await self._send_event(event)
        if event_id is not None:
            self._block_event_ids[block.header.hash] = authoring_event_id


    async def _handle_block_importing(self, payload) -> None:
        block = self._resolve_block(payload)
        if block is None:
            return

        block_hash = block.header.hash
        outline = self._build_block_outline(block)
        event = TelemetryBlockImportingEvent(
            timestamp=self._timestamp(),
            slot=block.header.timeslot,
            outline=outline,
        )
        event_id = await self._send_event(event)
        if event_id is not None:
            self._block_event_ids[block_hash] = event_id


    async def _handle_block_verified(self, payload) -> None:
        block = self._resolve_block(payload)
        if block is None:
            return
        block_hash = block.header.hash
        import_event_id = self._block_event_ids.get(block_hash)
        if import_event_id is None:
            logger.debug("Telemetry skip block verified: no import event id")
            return
        event = TelemetryBlockVerifiedEvent(
            timestamp=self._timestamp(),
            importing_event_id=import_event_id,
        )
        await self._send_event(event)


    async def _handle_block_verification_failed(self, payload) -> None:
        block = self._resolve_block(payload)
        if block is None:
            return
        reason = ""
        if isinstance(payload, dict):
            reason = str(payload.get("reason", ""))
        block_hash = block.header.hash
        import_event_id = self._block_event_ids.pop(block_hash, None)
        if import_event_id is None:
            logger.debug("Telemetry skip verification failed: no import event id")
            return
        event = TelemetryBlockVerificationFailedEvent(
            timestamp=self._timestamp(),
            importing_event_id=import_event_id,
            reason=reason or "verification failed",
        )
        await self._send_event(event)


    async def _handle_block_executed(self, payload) -> None:
        if not isinstance(payload, dict):
            return
        block = self._resolve_block(payload)
        if block is None:
            return
        stats = payload.get("accumulation_statistics", {})

        block_hash = block.header.hash
        correlated_event_id = self._block_event_ids.get(block_hash)

        if correlated_event_id is None:
            logger.debug("Telemetry skip block executed: no correlated event id")
            return

        service_costs = self._culculate_service_costs(stats)
        event = TelemetryBlockExecutedEvent(
            timestamp=self._timestamp(),
            correlated_event_id=correlated_event_id,
            service_costs=service_costs,
        )
        await self._send_event(event)
        self._block_event_ids.pop(block_hash, None)


    def _culculate_service_costs(self, stats: Dict[int, Dict[str, int]]) -> List[TelemetryServiceCost]:
        costs: List[TelemetryServiceCost] = []
        for service_id, values in stats.items():
            items = int(values.get("nr_work_reports_accumulated", 0))
            gas = int(values.get("total_gas_utilized", 0))
            cost = TelemetryAccumulateCost(
                accumulate_calls=items,
                transfers_processed=0,
                items_accumulated=items,
                total_exec=TelemetryExecCost(gas_used=gas, time_ns=0),
                compile_time_ns=0,
                read_write_exec=TelemetryExecCost(0, 0),
                lookup_exec=TelemetryExecCost(0, 0),
                network_exec=TelemetryExecCost(0, 0),
                config_exec=TelemetryExecCost(0, 0),
                transfer_exec=TelemetryExecCost(0, 0),
                transfer_gas=0,
                other_exec=TelemetryExecCost(0, 0),
            )
            costs.append(TelemetryServiceCost(service_id=service_id, accumulate_cost=cost))

        if len(costs) <= self.MAX_SERVICE_COST_ENTRIES:
            return costs

        # Combine lowest entries into aggregate as per specification.
        costs.sort(key=lambda c: (c.accumulate_cost.total_exec.gas_used, c.service_id))
        overflow = costs[:- (self.MAX_SERVICE_COST_ENTRIES - 1)]
        keep = costs[- (self.MAX_SERVICE_COST_ENTRIES - 1):]

        aggregate = self._aggregate_service_costs(overflow)
        keep.append(aggregate)
        return keep


    @staticmethod
    def _aggregate_service_costs(costs: Iterable[TelemetryServiceCost]) -> TelemetryServiceCost:
        accumulate_calls = 0
        transfers_processed = 0
        items_accumulated = 0
        total_gas = 0

        for cost in costs:
            data = cost.accumulate_cost
            accumulate_calls += data.accumulate_calls
            transfers_processed += data.transfers_processed
            items_accumulated += data.items_accumulated
            total_gas += data.total_exec.gas_used

        aggregate_cost = TelemetryAccumulateCost(
            accumulate_calls=accumulate_calls,
            transfers_processed=transfers_processed,
            items_accumulated=items_accumulated,
            total_exec=TelemetryExecCost(gas_used=total_gas, time_ns=0),
            compile_time_ns=0,
            read_write_exec=TelemetryExecCost(0, 0),
            lookup_exec=TelemetryExecCost(0, 0),
            network_exec=TelemetryExecCost(0, 0),
            config_exec=TelemetryExecCost(0, 0),
            transfer_exec=TelemetryExecCost(0, 0),
            transfer_gas=0,
            other_exec=TelemetryExecCost(0, 0),
        )
        return TelemetryServiceCost(service_id=0xFFFFFFFF, accumulate_cost=aggregate_cost)


    def _resolve_block(self, payload) -> Optional[Block]:
        if isinstance(payload, dict):
            block = payload.get("block")
        else:
            block = payload
        if isinstance(block, Block):
            return block
        logger.debug("Telemetry handler received unexpected payload: %r", payload)
        return None


    def _build_block_outline(self, block: Block) -> TelemetryBlockOutline:
        block_bytes = block.to_jam_bytes().to_bytes()
        preimages = block.extrinsic.preimages
        preimages_bytes = sum(len(p.blob) for p in preimages)
        header_hash = block.header.hash
        return TelemetryBlockOutline(
            size_bytes=len(block_bytes),
            header_hash=header_hash,
            tickets=len(block.extrinsic.tickets),
            preimages=len(preimages),
            preimages_bytes=preimages_bytes,
            guarantees=len(block.extrinsic.guarantees),
            assurances=len(block.extrinsic.assurances),
            dispute_verdicts=len(block.extrinsic.disputes.verdicts),
        )


    async def _send_event(self, event) -> Optional[int]:
        if not self._connection or not self._connection.is_connected():
            return None
        encoded = event.to_jam_bytes().to_bytes()
        frame = len(encoded).to_bytes(4, "little") + encoded
        async with self._send_lock:
            if not self._connection or not self._connection.is_connected():
                return None
            event_id = self._next_event_id
            try:
                await self._connection.send(frame)
            except (TelemetryConnectionError, OSError) as exc:
                logger.warning("Telemetry send failed: %s", exc)
                self._connection_lost.set()
                return None
            else:
                self._next_event_id += 1
                return event_id


    async def _send_raw(self, message) -> None:
        if not self._connection or not self._connection.is_connected():
            return
        encoded = message.to_jam_bytes().to_bytes()
        frame = len(encoded).to_bytes(4, "little") + encoded
        try:
            await self._connection.send(frame)
        except (TelemetryConnectionError, OSError) as exc:
            logger.warning("Telemetry send failed: %s", exc)
            self._connection_lost.set()


    def create_parameters(self) -> TelemetryJamParameters:
        v1 = TelemetryJamParametersV1(
            deposit_per_item=gp_const.MINIMUM_BALANCE_ITEM,
            deposit_per_byte=gp_const.MINIMUM_BALANCE_OCTET,
            deposit_per_account=gp_const.MINIMUM_BALANCE_SERVICE,
            core_count=gp_const.CORE_COUNT,
            min_turnaround_period=gp_const.PREIMAGE_EXPUNGE_TIMESLOTS,
            epoch_period=gp_const.EPOCH_TIMESLOTS,
            max_accumulate_gas=gp_const.GAS_ACCUMULATION,
            max_is_authorized_gas=gp_const.GAS_INVOKE,
            max_refine_gas=gp_const.GAS_REFINE,
            block_gas_limit=gp_const.GAS_TOTAL,
            recent_block_count=gp_const.HISTORY,
            max_work_items=gp_const.MAXIMUM_WORK_ITEMS,
            max_dependencies=gp_const.MAXIMUM_DEPENDENCIES_WORK_REPORT,
            max_tickets_per_block=gp_const.MAXIMUM_EXTRINSIC_TICKETS,
            max_lookup_anchor_age=gp_const.MAXIMUM_AGE_LOOKUP_ANCHOR,
            tickets_attempts_number=gp_const.TICKET_ENTRIES,
            auth_window=gp_const.MAXIMIM_AUTHORIZATION_POOL_ITEMS,
            slot_period_sec=gp_const.SLOT_PERIOD,
            auth_queue_len=gp_const.MAXIMUM_AUTHORIZATION_QUEUE_ITEMS,
            rotation_period=gp_const.ROTATION_PERIOD_CORE,
            max_extrinsics=gp_const.MAXIMUM_NUMBER_EXTRINSICS_WORK_PACKAGE,
            availability_timeout=gp_const.UNAVAILABLE_WORK_REPLACEMENT_PERIOD,
            val_count=gp_const.VALIDATOR_COUNT,
            max_authorizer_code_size=gp_const.MAXIMUM_SIZE_IS_AUTH_CODE,
            max_input=gp_const.MAXIMUM_SIZE_WORK_PACKAGE,
            max_service_code_size=gp_const.MAXIMUM_SIZE_SERVICE_CODE,
            basic_piece_len=gp_const.SIZE_ERASURE_CODED_PIECES,
            max_imports=gp_const.MAXIMUM_NUMBER_IMPORTS_WORK_PACKAGE,
            segment_piece_count=gp_const.MAXIMUM_SIZE_ENCODED_WORK_PACKAGE,
            max_report_elective_data=gp_const.MAXIMUM_SIZE_ENCODED_WORK_REPORT,
            transfer_memo_size=gp_const.SIZE_TRANSFER_MEMO,
            max_exports=gp_const.MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE,
            epoch_tail_start=gp_const.TICKET_SUBMISSION_END_SLOT,
        )
        return TelemetryJamParameters(V1=v1)


    def create_peer_address(self) -> TelemetryPeerAddress:
        if not self._local_address:
            return TelemetryPeerAddress(ip=bytes(16), port=self._local_port or 0)
        try:
            ip = ipaddress.ip_address(self._local_address)
        except ValueError:
            logger.warning("Invalid telemetry local address: %s", self._local_address)
            return TelemetryPeerAddress(ip=bytes(16), port=self._local_port or 0)

        if ip.version == 4:
            ipv6 = ipaddress.IPv6Address("::ffff:" + str(ip))
        else:
            ipv6 = ip
        return TelemetryPeerAddress(ip=ipv6.packed, port=self._local_port or 0)


    def _timestamp(self) -> int:
        common_era = getattr(self.app.config, "common_era", 0)
        return max(0, int((time.time() - common_era) * 1_000_000))
