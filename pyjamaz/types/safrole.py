from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Union, Type

from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS, VALIDATOR_COUNT
from pyjamaz.mixins import SerializableMixin, T
from scalecodec.base import ScaleTypeDef, ScaleType
from scalecodec.exceptions import ScaleSerializeException
from scalecodec.types import Enum as ScaleEnum, H256, U8 as ScaleU8, Array, Option, U32 as ScaleU32, Vec, Struct

U8 = int  # INTEGER (0..255)
U32 = int  # INTEGER (0..4294967295)
ByteArray32 = bytes  # SEQUENCE (SIZE(32)) OF U8
ByteArray128 = bytes
ByteArray144 = bytes
ByteArray784 = bytes
OpaqueHash = ByteArray32
Ed25519Key = ByteArray32
BlsKey = ByteArray144  # SEQUENCE (SIZE(144)) OF U8
BandersnatchKey = ByteArray32
EpochKeys = List[BandersnatchKey]  # SEQUENCE (SIZE(epoch-length)) OF BandersnatchKey


class CustomErrorCode(SerializableMixin, Enum):
    bad_slot = 0  # Timeslot value must be strictly monotonic.
    unexpected_ticket = 1  # Received a ticket while in epoch's tail.
    bad_ticket_order = 2  # Tickets must be sorted.
    bad_ticket_proof = 3  # Invalid ticket ring proof.
    bad_ticket_attempt = 4  # Invalid ticket attempt value.
    reserved = 5  # Reserved
    duplicate_ticket = 6  # Found a ticket duplicate.
    too_many_tickets = 7  # Found amount of tickets > K

    @classmethod
    def scale_type_def(cls) -> ScaleTypeDef:
        return ScaleEnum(**{status.name: None for status in cls})

    def to_scale_type(self) -> ScaleType:
        scale_type = self.scale_type_def().new()
        scale_type.deserialize(self.name)
        return scale_type

    @classmethod
    def from_scale_type(cls, scale_type: ScaleType) -> "CustomErrorCode":
        return cls[scale_type.value]


@dataclass
class TicketBody(SerializableMixin):
    id: OpaqueHash = field(metadata={'scale': H256})  # OpaqueHash
    attempt: U8 = field(metadata={'scale': ScaleU8})   # U8


TicketsBodies = List[TicketBody]  # SEQUENCE (SIZE(epoch-length)) OF TicketBody


@dataclass
class SlotSealerSeries(SerializableMixin):
    tickets: Optional[List[TicketBody]] = field(default_factory=list)  # Optional list of TicketBody instances
    keys: Optional[List[BandersnatchKey]] = field(default_factory=list)  # Optional list of BandersnatchKey instances

    @classmethod
    def scale_type_def(cls):
        return ScaleEnum(
            tickets=Array(TicketBody.scale_type_def(), EPOCH_TIMESLOTS),
            keys=Array(H256, EPOCH_TIMESLOTS)
        )

    def serialize(self) -> Union[str, int, float, bool, dict, list]:
        if self.tickets:
            return {'tickets': [t.serialize() for t in self.tickets]}
        elif self.keys:
            return {'keys': [f"0x{k.hex()}" for k in self.keys]}
        else:
            raise ScaleSerializeException("Neither tickets nor keys were provided")


@dataclass
class ValidatorData(SerializableMixin):
    bandersnatch: BandersnatchKey = field(metadata={'scale': H256})
    ed25519: Ed25519Key = field(metadata={'scale': H256})
    bls: BlsKey = field(metadata={'scale': Array(ScaleU8, 144)})
    metadata: ByteArray128 = field(metadata={'scale': Array(ScaleU8, 128)})

    #
    # def to_scale_type(self) -> 'ValidatorKeysObject':
    #     # Create a new instance of the scale type using the scale_type_def metadata.
    #     scale_type = self._scale_type_def.new()
    #     # Deserialize the keys and metadata into the scale type.
    #     scale_type.deserialize({
    #         'bs_key': self.bandersnatch,  # GP-ref:52,vb
    #         'ed25519_key': self.ed25519,  # GP-ref:53,ve
    #         'bls_key': self.bls,  # GP-ref:54,vBLS
    #         'metadata': self.metadata  # GP-ref:55,vm
    #     })
    #     return scale_type
    #
    # @classmethod
    # def from_scale_type(cls, scale_type: ValidatorKeysObject):
    #     return cls(
    #         bandersnatch=scale_type.value_object['bs_key'].to_bytes(),
    #         ed25519=scale_type.value_object['ed25519_key'].to_bytes(),
    #         bls=scale_type.value_object['bls_key'].to_bytes(),
    #         metadata=scale_type.value_object['metadata'].to_bytes(),
    #     )


ValidatorsData = List[ValidatorData]  # SEQUENCE (SIZE(validators-count)) OF ValidatorData


@dataclass
class TicketEnvelope(SerializableMixin):
    attempt: U8 = field(metadata={'scale': ScaleU8})
    signature: ByteArray784 = field(metadata={'scale': Array(ScaleU8, 784)})

    def __post_init__(self):
        # Validate that attempt is a valid U8 integer
        if not isinstance(self.attempt, int) or not (0 <= self.attempt <= 255):
            raise ValueError("Attempt must be an integer between 0 and 255")

        # Validate that signature is a valid ByteArray784
        if not isinstance(self.signature, (bytes, bytearray)) or len(self.signature) != 784:
            raise ValueError("Signature must be a bytes object of length 784")


@dataclass
class EpochMark(SerializableMixin):
    entropy: OpaqueHash = field(metadata={'scale': H256})
    validators: List[BandersnatchKey] = field(metadata={'scale': Array(H256, VALIDATOR_COUNT)})


TicketsMark = List[TicketBody]  # SEQUENCE (SIZE(epoch-length)) OF TicketBody


@dataclass
class OutputMarks(SerializableMixin):
    epoch_mark: Optional[EpochMark] = None  # New epoch signal. OPTIONAL
    tickets_mark: Optional[TicketsMark] = field(default=None, metadata={'scale': Option(Array(TicketBody.scale_type_def(), EPOCH_TIMESLOTS))})  # Tickets signal. OPTIONAL


@dataclass
class State(SerializableMixin):
    tau: U32 = field(metadata={'scale': ScaleU32})                # Most recent block's timeslot.
    eta: List[OpaqueHash] = field(metadata={'scale': Array(H256, 4)})  # SEQUENCE (SIZE(4)) OF OpaqueHash
    lambda_: ValidatorsData = field(metadata={'scale': Array(ValidatorData.scale_type_def(), VALIDATOR_COUNT)}) # Validator keys and metadata which were active in the prior epoch.
    kappa: ValidatorsData = field(metadata={'scale': Array(ValidatorData.scale_type_def(), VALIDATOR_COUNT)}) # Validator keys and metadata currently active.
    gamma_k: ValidatorsData = field(metadata={'scale': Array(ValidatorData.scale_type_def(), VALIDATOR_COUNT)})  # Validator keys for the following epoch.
    iota: ValidatorsData = field(metadata={'scale': Array(ValidatorData.scale_type_def(), VALIDATOR_COUNT)})  # Validator keys and metadata to be drawn from next.
    gamma_a: TicketsBodies = field(metadata={'scale': Vec(TicketBody.scale_type_def())})  # Sealing-key contest ticket accumulator.
    gamma_s: SlotSealerSeries  # Sealing-key series of the current epoch.
    gamma_z: ByteArray144 = field(metadata={'scale': Array(ScaleU8, 144)})  # Bandersnatch ring commitment.


@dataclass
class Input(SerializableMixin):
    slot: U32 = field(metadata={'scale': ScaleU32})  # Current slot. U32
    entropy: OpaqueHash = field(metadata={'scale': H256}) # Per block entropy (originated from block entropy source VRF)
    extrinsic: List[TicketEnvelope]  # Safrole extrinsic. SEQUENCE (SIZE(0..16)) OF TicketEnvelope

    @classmethod
    def scale_type_def(cls):
        return Struct(slot=ScaleU32, entropy=H256, extrinsic=Vec(TicketEnvelope.scale_type_def()))


@dataclass
class Output(SerializableMixin):
    ok: Optional[OutputMarks] = None  # Markers
    err: Optional[CustomErrorCode] = None  # Error code (not specified in the Graypaper)

    @classmethod
    def scale_type_def(cls):

        return ScaleEnum(
            ok=OutputMarks.scale_type_def(),
            err=CustomErrorCode.scale_type_def()
        )

    def to_scale_type(self) -> ScaleType:
        scale_type = self.scale_type_def().new()
        scale_type.deserialize(self.serialize())
        return scale_type

    @classmethod
    def deserialize(cls: Type[T], data: Union[str, int, float, bool, dict, list]) -> T:

        return super().deserialize(data)

    def serialize(self) -> Union[str, int, float, bool, dict, list]:
        if self.err is not None:
            return {'err': self.err.serialize()}
        else:
            return {'ok': self.ok.serialize()}
