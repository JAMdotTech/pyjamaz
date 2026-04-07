from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Optional, Protocol, TYPE_CHECKING

logger = logging.getLogger("pyjamaz.transport.jamnp_s")

if TYPE_CHECKING:
    from pyjamaz.transport.jamnp_s.connection import JAMConnection


class StreamKind(IntEnum):
    UP0_BlockAnnouncement = 0
    CE128_BlockRequest = 128
    CE129_StateRequest = 129
    CE131_SafroleTicketDistributionStep1 = 131
    CE132_SafroleTicketDistributionStep2 = 132
    CE133_WorkPackageSubmission = 133
    CE134_WorkPackageSharing = 134
    CE135_WorkReportDistribution = 135
    CE136_WorkReportRequest = 136
    CE137_ShardDistribution = 137
    CE138_AuditShardRequest = 138
    CE139_SegmentShardRequest = 139
    CE140_SegmentShardRequestJustification = 140
    CE141_AssuranceDistribution = 141
    CE142_PreimageAnnouncement = 142
    CE143_PreimageRequest = 143
    CE144_AuditAnnouncement = 144
    CE145_JudgmentPublication = 145


class StreamDirection(Enum):
    initiator = 0
    acceptor = 1


class IStreamHandler(Protocol):
    kind: StreamKind

    def init_stream(self, stream: "ManagedStream") -> None:
        ...

    def on_message(self, stream: "ManagedStream", data: bytes) -> None:
        ...

    def on_fin(self, stream: "ManagedStream") -> None:
        ...

    def on_reset(self, stream: "ManagedStream", reset_code: int) -> None:
        ...

    def on_close(self, stream: "ManagedStream") -> None:
        ...


@dataclass
class ManagedStream:
    stream_id: int
    stream_kind: StreamKind
    conn: "JAMConnection"
    direction: StreamDirection
    handler: Optional[IStreamHandler] = field(default=None, repr=False)
    closed: bool = False
    recv_buffer: bytearray = field(default_factory=bytearray, repr=False)
    expected_len: Optional[int] = field(default=None, repr=False)
    stream_type: int = field(init=False)
    stream_type_byte: bytes = field(init=False)

    ERROR_GENERAL = 1
    ERROR_INVALID_MESSAGE = 2
    ERROR_INVALID_SIZE = 3
    ERROR_TOO_LARGE = 4
    ERROR_VALIDATION_FAILED = 5

    def __post_init__(self) -> None:
        self.stream_type = int(self.stream_kind)
        self.stream_type_byte = self.stream_type.to_bytes(length=1, byteorder="little")

    @property
    def protocol(self):
        return self.conn.protocol

    @property
    def stream_key(self):
        return self.conn.jam_connection_ulid, self.stream_id

    def create_message(self, payload: bytes, add_stream_type: bool = False) -> bytes:
        msg = len(payload).to_bytes(length=4, byteorder="little") + payload
        if add_stream_type:
            return self.stream_type_byte + msg
        return msg

    def close(self, reason: int = 0, clean_close: bool = True) -> None:
        if self.closed:
            return
        self.conn.stream_manager.close_stream(self, reason=reason, clean_close=clean_close)

    def send_reset(self, reset_code: int) -> None:
        if self.closed:
            return
        self.conn.stream_manager.send_reset(self, reset_code)

    def handle_error(self, exc: Exception) -> None:
        if isinstance(exc, ValueError):
            code = self.ERROR_INVALID_MESSAGE
        elif isinstance(exc, MemoryError):
            code = self.ERROR_TOO_LARGE
        else:
            code = self.ERROR_GENERAL

        logger.error(f"Stream {self.stream_id} error: {exc}")
        self.send_reset(code)
