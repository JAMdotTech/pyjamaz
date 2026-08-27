from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from jamcodec.mixins import Serializable
from jamcodec.types import Array, String, U16, U32, U64, U8, Vec

from pyjamaz.graypaper_constants import CORE_COUNT


def check_length(value: str, max_length: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) > max_length:
        raise ValueError(f"Value '{value}' exceeds maximum length {max_length}")
    return value


@dataclass
class TelemetryPeerAddress(Serializable):
    ip: bytes = field(metadata={"codec": Array(U8, 16)})
    port: int = field(metadata={"codec": U16})


@dataclass
class TelemetryJamParametersV1(Serializable):
    deposit_per_item: int = field(metadata={"codec": U64})
    deposit_per_byte: int = field(metadata={"codec": U64})
    deposit_per_account: int = field(metadata={"codec": U64})
    core_count: int = field(metadata={"codec": U16})
    min_turnaround_period: int = field(metadata={"codec": U32})
    epoch_period: int = field(metadata={"codec": U32})
    max_accumulate_gas: int = field(metadata={"codec": U64})
    max_is_authorized_gas: int = field(metadata={"codec": U64})
    max_refine_gas: int = field(metadata={"codec": U64})
    block_gas_limit: int = field(metadata={"codec": U64})
    recent_block_count: int = field(metadata={"codec": U16})
    max_work_items: int = field(metadata={"codec": U16})
    max_dependencies: int = field(metadata={"codec": U16})
    max_tickets_per_block: int = field(metadata={"codec": U16})
    max_lookup_anchor_age: int = field(metadata={"codec": U32})
    tickets_attempts_number: int = field(metadata={"codec": U16})
    auth_window: int = field(metadata={"codec": U16})
    slot_period_sec: int = field(metadata={"codec": U16})
    auth_queue_len: int = field(metadata={"codec": U16})
    rotation_period: int = field(metadata={"codec": U16})
    max_extrinsics: int = field(metadata={"codec": U16})
    availability_timeout: int = field(metadata={"codec": U16})
    val_count: int = field(metadata={"codec": U16})
    max_authorizer_code_size: int = field(metadata={"codec": U32})
    max_input: int = field(metadata={"codec": U32})
    max_service_code_size: int = field(metadata={"codec": U32})
    basic_piece_len: int = field(metadata={"codec": U32})
    max_imports: int = field(metadata={"codec": U32})
    segment_piece_count: int = field(metadata={"codec": U32})
    max_report_elective_data: int = field(metadata={"codec": U32})
    transfer_memo_size: int = field(metadata={"codec": U32})
    max_exports: int = field(metadata={"codec": U32})
    epoch_tail_start: int = field(metadata={"codec": U32})


@dataclass
class TelemetryJamParameters(Serializable):
    V1: TelemetryJamParametersV1 = field(metadata={"codec": TelemetryJamParametersV1.to_codec_def()})


@dataclass
class TelemetryNodeInfo(Serializable):
    protocol_version: int = field(default=1, kw_only=True, metadata={"codec": U8})
    parameters: TelemetryJamParameters = field(metadata={"codec": TelemetryJamParameters.to_codec_def()})
    genesis_hash: bytes = field(metadata={"codec": Array(U8, 32)})
    peer_id: bytes = field(metadata={"codec": Array(U8, 32)})
    peer_address: TelemetryPeerAddress = field(metadata={"codec": TelemetryPeerAddress.to_codec_def()})
    node_flags: int = field(metadata={"codec": U32})
    implementation_name: str = field(metadata={"codec": String})
    implementation_version: str = field(metadata={"codec": String})
    graypaper_version: str = field(metadata={"codec": String})
    note: str = field(metadata={"codec": String})

    def __post_init__(self) -> None:
        check_length(self.implementation_name, 32)
        check_length(self.implementation_version, 32)
        check_length(self.graypaper_version, 16)
        check_length(self.note, 512)
        if len(self.peer_id) != 32:
            raise ValueError("Peer ID must be 32 bytes")


@dataclass
class TelemetryStatusEvent(Serializable):
    timestamp: int = field(metadata={"codec": U64})
    event_type: int = field(default=10, kw_only=True, metadata={"codec": U8})
    total_peers: int = field(metadata={"codec": U32})
    validator_peers: int = field(metadata={"codec": U32})
    block_announcement_peers: int = field(metadata={"codec": U32})
    guarantees_by_core: List[int] = field(metadata={"codec": Array(U8, CORE_COUNT)})
    availability_shards: int = field(metadata={"codec": U32})
    availability_shards_size: int = field(metadata={"codec": U64})
    preimages_ready: int = field(metadata={"codec": U32})
    preimages_ready_size: int = field(metadata={"codec": U32})


@dataclass
class TelemetryBlockOutline(Serializable):
    size_bytes: int = field(metadata={"codec": U32})
    header_hash: bytes = field(metadata={"codec": Array(U8, 32)})
    tickets: int = field(metadata={"codec": U32})
    preimages: int = field(metadata={"codec": U32})
    preimages_bytes: int = field(metadata={"codec": U32})
    guarantees: int = field(metadata={"codec": U32})
    assurances: int = field(metadata={"codec": U32})
    dispute_verdicts: int = field(metadata={"codec": U32})


@dataclass
class TelemetryBlockImportingEvent(Serializable):
    timestamp: int = field(metadata={"codec": U64})
    event_type: int = field(default=43, kw_only=True, metadata={"codec": U8})
    slot: int = field(metadata={"codec": U32})
    outline: TelemetryBlockOutline = field(metadata={"codec": TelemetryBlockOutline.to_codec_def()})


@dataclass
class TelemetryBlockAuthoringEvent(Serializable):
    timestamp: int = field(metadata={"codec": U64})
    event_type: int = field(default=40, kw_only=True, metadata={"codec": U8})
    slot: int = field(metadata={"codec": U32})
    parent_hash: bytes = field(metadata={"codec": Array(U8, 32)})


@dataclass
class TelemetryBlockAuthoredEvent(Serializable):
    timestamp: int = field(metadata={"codec": U64})
    event_type: int = field(default=42, kw_only=True, metadata={"codec": U8})
    authoring_event_id: int = field(metadata={"codec": U64})
    outline: TelemetryBlockOutline = field(metadata={"codec": TelemetryBlockOutline.to_codec_def()})


@dataclass
class TelemetryBlockVerificationFailedEvent(Serializable):
    timestamp: int = field(metadata={"codec": U64})
    event_type: int = field(default=44, kw_only=True, metadata={"codec": U8})
    importing_event_id: int = field(metadata={"codec": U64})
    reason: str = field(metadata={"codec": String})

    def __post_init__(self) -> None:
        check_length(self.reason, 128)


@dataclass
class TelemetryBlockVerifiedEvent(Serializable):
    timestamp: int = field(metadata={"codec": U64})
    event_type: int = field(default=45, kw_only=True, metadata={"codec": U8})
    importing_event_id: int = field(metadata={"codec": U64})


@dataclass
class TelemetryExecCost(Serializable):
    gas_used: int = field(metadata={"codec": U64})
    time_ns: int = field(metadata={"codec": U64})


@dataclass
class TelemetryAccumulateCost(Serializable):
    accumulate_calls: int = field(metadata={"codec": U32})
    transfers_processed: int = field(metadata={"codec": U32})
    items_accumulated: int = field(metadata={"codec": U32})
    total_exec: TelemetryExecCost = field(metadata={"codec": TelemetryExecCost.to_codec_def()})
    compile_time_ns: int = field(metadata={"codec": U64})
    read_write_exec: TelemetryExecCost = field(metadata={"codec": TelemetryExecCost.to_codec_def()})
    lookup_exec: TelemetryExecCost = field(metadata={"codec": TelemetryExecCost.to_codec_def()})
    network_exec: TelemetryExecCost = field(metadata={"codec": TelemetryExecCost.to_codec_def()})
    config_exec: TelemetryExecCost = field(metadata={"codec": TelemetryExecCost.to_codec_def()})
    transfer_exec: TelemetryExecCost = field(metadata={"codec": TelemetryExecCost.to_codec_def()})
    transfer_gas: int = field(metadata={"codec": U64})
    other_exec: TelemetryExecCost = field(metadata={"codec": TelemetryExecCost.to_codec_def()})


@dataclass
class TelemetryServiceCost(Serializable):
    service_id: int = field(metadata={"codec": U32})
    accumulate_cost: TelemetryAccumulateCost = field(metadata={"codec": TelemetryAccumulateCost.to_codec_def()})


@dataclass
class TelemetryBlockExecutedEvent(Serializable):
    timestamp: int = field(metadata={"codec": U64})
    event_type: int = field(default=47, kw_only=True, metadata={"codec": U8})
    correlated_event_id: int = field(metadata={"codec": U64})
    service_costs: List[TelemetryServiceCost] = field(
        metadata={"codec": Vec(TelemetryServiceCost.to_codec_def())}
    )
