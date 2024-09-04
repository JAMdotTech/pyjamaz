from dataclasses import dataclass, field
from typing import List, Optional

from jamcodec.types import H256, U32, Option, Vec, Array, U8, U16, Bool
from pyjamaz.graypaper_constants import VALIDATOR_COUNT, EPOCH_TIMESLOTS
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.types.common import OpaqueHash, BandersnatchKey, ByteArray784

from jamcodec.mixins import Serializable


@dataclass
class TicketBody(Serializable):
    id: OpaqueHash = field(metadata={'codec': H256})  # OpaqueHash
    attempt: int = field(metadata={'codec': U8})   # U8


@dataclass
class EpochMark(Serializable):
    entropy: OpaqueHash = field(metadata={'codec': H256})
    validators: List[BandersnatchKey] = field(metadata={'codec': Array(H256, VALIDATOR_COUNT)})


@dataclass
class TicketEnvelope(Serializable):
    attempt: int = field(metadata={'codec': U8})
    signature: ByteArray784 = field(metadata={'codec': Array(U8, 784)})

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
    epoch_mark: Optional[EpochMark] = field(default=None, metadata={'codec': Option(EpochMark.to_codec_def())})   # New epoch signal. OPTIONAL
    tickets_mark: Optional[TicketsMark] = field(default=None, metadata={'codec': Option(Array(TicketBody.to_codec_def(), EPOCH_TIMESLOTS))})  # Tickets signal. OPTIONAL


@dataclass
class Header(Serializable):
    """
    Header type
    """
    parent: bytes = field(metadata={'codec': H256})                      # GP-0.3.6-ref:38 Hp
    parent_state_root: bytes = field(metadata={'codec': H256})                # GP-0.3.6-ref:42 Hr
    extrinsic_hash: bytes = field(metadata={'codec': H256})                   # GP-0.3.6-ref:40 Hx
    timeslot: int = field(metadata={'codec': U32})                           # GP-0.3.6-ref:41 Ht
    epoch_marker: Optional[EpochMark] = field(metadata={'codec': Option(EpochMark.to_codec_def())}) # GP-0.3.6-ref:44 He
    tickets_marker: Optional[TicketsMark] = field(metadata={'codec': Option(Array(TicketBody.to_codec_def(), EPOCH_TIMESLOTS))}) # GP-0.3.6-ref:44 Hw
    offenders_marker: List[bytes] = field(metadata={'codec': Vec(H256)})   # GP-0.3.6-ref:44 Ho
    author_index: int = field(metadata={'codec': U16})                 # GP-0.3.6-ref:43 Hi
    entropy_source: bytes = field(metadata={'codec': Array(U8, 96)})                   # GP-0.3.6-ref:41 Hv entropy-yielding VRF
    seal: bytes = field(metadata={'codec': Array(U8, 96)})                      # GP-0.3.6-ref:?? Hs

    def generate_header_hash(self) -> bytes:
        return blake2b_256_hash(self.to_jam_bytes().to_bytes())


@dataclass
class Extrinsic(Serializable):
    tickets: List[TicketEnvelope] = field(metadata={'codec': Vec(TicketEnvelope.to_codec_def())})
    # TODO TEMP unclear, move when Extrinsic is fully defined
    work_report_hashes: Optional[List[bytes]] = field(metadata={'codec': Option(Vec(H256))})
    accumulate_root: Optional[bytes] = field(metadata={'codec': Option(H256)})


@dataclass
class Block(Serializable):
    header: Header = field(metadata={'codec': Header.to_codec_def()})
    extrinsic: Extrinsic = field(metadata={'codec': Extrinsic.to_codec_def()})
