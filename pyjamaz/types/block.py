from dataclasses import dataclass, field
from typing import List, Optional

from pyjamaz.graypaper_constants import VALIDATOR_COUNT, EPOCH_TIMESLOTS
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.types.common import H256, OpaqueHash, U8, BandersnatchKey, ByteArray784

from pyjamaz.serialization import Serializable


@dataclass
class TicketBody(Serializable):
    id: OpaqueHash = field(metadata={'length': 32})  # OpaqueHash
    attempt: U8 = field(metadata={'length': 1})   # U8


@dataclass
class EpochMark(Serializable):
    entropy: OpaqueHash = field(metadata={'length': 32})
    validators: List[BandersnatchKey] = field(metadata={'length': 32, 'size': VALIDATOR_COUNT})


@dataclass
class TicketEnvelope(Serializable):
    attempt: U8 = field(metadata={'length': 1})
    signature: ByteArray784 = field(metadata={'length': 784})

    def __post_init__(self):
        # Validate that attempt is a valid U8 integer
        if not isinstance(self.attempt, int) or not (0 <= self.attempt <= 255):
            raise ValueError("Attempt must be an integer between 0 and 255")

        # Validate that signature is a valid ByteArray784
        if not isinstance(self.signature, (bytes, bytearray)) or len(self.signature) != 784:
            raise ValueError("Signature must be a bytes object of length 784")


TicketsMark = List[TicketBody]  # SEQUENCE (SIZE(epoch-length)) OF TicketBody


@dataclass
class OutputMarks(Serializable):
    epoch_mark: Optional[EpochMark] = None  # New epoch signal. OPTIONAL
    tickets_mark: Optional[TicketsMark] = field(default=None, metadata={'size': EPOCH_TIMESLOTS})  # Tickets signal. OPTIONAL


@dataclass
class Header(Serializable):
    hash: Optional[H256] = field(metadata={'length': 32})
    parent_hash: H256 = field(metadata={'length': 32})                      # GP-0.3.6-ref:38 Hp
    parent_state_root: H256 = field(metadata={'length': 32})                # GP-0.3.6-ref:42 Hr
    extrinsic_root: H256 = field(metadata={'length': 32})                   # GP-0.3.6-ref:40 Hx
    timeslot: int = field(metadata={'length': 4})                           # GP-0.3.6-ref:41 Ht
    epoch_marker: Optional[EpochMark]                                       # GP-0.3.6-ref:44 He
    tickets_marker: Optional[TicketsMark]                                   # GP-0.3.6-ref:44 Hw
    offenders_marker: List[bytes] = field(metadata={'size': 'offenders_marker', 'length': 32})   # GP-0.3.6-ref:44 Ho
    block_author_index: int = field(metadata={'length': 4})                 # GP-0.3.6-ref:43 Hi
    vrf_signature: bytes = field(metadata={'length': 32})                   # GP-0.3.6-ref:41 Hv entropy-yielding VRF
    block_seal: bytes = field(metadata={'length': 32})                      # GP-0.3.6-ref:?? Hs

    def generate_header_hash(self):
        self.hash = None
        self.hash = blake2b_256_hash(self.to_jam_bytes().to_bytes())


@dataclass
class Extrinsic(Serializable):
    tickets: List[TicketEnvelope] = field(metadata={})
    # TODO TEMP unclear, move when Extrinsic is fully defined
    work_report_hashes: Optional[List[H256]] = field(metadata={'size': 'work_report_hashes', 'length': 32})
    accumulate_root: Optional[H256] = field(metadata={'length': 32})


@dataclass
class Block(Serializable):
    header: Header
    extrinsic: Extrinsic
