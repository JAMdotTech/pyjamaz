from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Type, Union

from pyjamaz.mixins import SerializableMixin, T
from scalecodec.base import ScaleTypeDef, ScaleType
from scalecodec.exceptions import ScaleSerializeException
from scalecodec.types import Struct, Option, Bytes, Array, U8 as ScaleU8, Vec, H256, Enum as ScaleEnum

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
    id: OpaqueHash  # OpaqueHash
    attempt: U8     # U8


TicketsBodies = List[TicketBody]  # SEQUENCE (SIZE(epoch-length)) OF TicketBody


@dataclass
class SlotSealerSeries(SerializableMixin):
    tickets: Optional[List[TicketBody]] = field(default_factory=list)  # Optional list of TicketBody instances
    keys: Optional[List[BandersnatchKey]] = field(default_factory=list)  # Optional list of BandersnatchKey instances

    @classmethod
    def scale_type_def(cls):
        return ScaleEnum(
            tickets=Vec(TicketBody.scale_type_def()),
            keys=Vec(H256)
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
    bandersnatch: BandersnatchKey  # Use forward references if these types are not yet defined in the current scope.
    ed25519: Ed25519Key
    bls: BlsKey
    metadata: ByteArray128

    @classmethod
    def scale_type_def(cls):
        return Struct(
            bandersnatch=H256,
            ed25519=H256,
            bls=Array(ScaleU8, 144),
            metadata=Array(ScaleU8, 128),
        )

    # _scale_type_def = ValidatorKeys()
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
    attempt: U8  # U8
    signature: ByteArray784  # SEQUENCE (SIZE(784)) OF U8

    def __post_init__(self):
        # Validate that attempt is a valid U8 integer
        if not isinstance(self.attempt, int) or not (0 <= self.attempt <= 255):
            raise ValueError("Attempt must be an integer between 0 and 255")

        # Validate that signature is a valid ByteArray784
        if not isinstance(self.signature, bytes) or len(self.signature) != 784:
            raise ValueError("Signature must be a bytes object of length 784")


@dataclass
class EpochMark(SerializableMixin):
    entropy: OpaqueHash  # OpaqueHash
    validators: List[BandersnatchKey]  # SEQUENCE (SIZE(validators-count)) OF BandersnatchKey


TicketsMark = List[TicketBody]  # SEQUENCE (SIZE(epoch-length)) OF TicketBody


@dataclass
class OutputMarks(SerializableMixin):
    epoch_mark: Optional[EpochMark] = None  # New epoch signal. OPTIONAL
    tickets_mark: Optional[TicketsMark] = None  # Tickets signal. OPTIONAL


@dataclass
class State(SerializableMixin):
    tau: U32  # Most recent block's timeslot.
    eta: List[OpaqueHash]  # SEQUENCE (SIZE(4)) OF OpaqueHash
    lambda_: ValidatorsData  # Validator keys and metadata which were active in the prior epoch.
    kappa: ValidatorsData  # Validator keys and metadata currently active.
    gamma_k: ValidatorsData  # Validator keys for the following epoch.
    iota: ValidatorsData  # Validator keys and metadata to be drawn from next.
    gamma_a: TicketsBodies  # Sealing-key contest ticket accumulator. SEQUENCE (SIZE(0..epoch-length)) OF TicketBody
    gamma_s: SlotSealerSeries  # Sealing-key series of the current epoch.
    gamma_z: ByteArray144  # Bandersnatch ring commitment. SEQUENCE (SIZE(144)) OF U8


@dataclass
class Input(SerializableMixin):
    slot: U32  # Current slot. U32
    entropy: OpaqueHash  # Per block entropy (originated from block entropy source VRF). OpaqueHash
    extrinsic: List[TicketEnvelope]  # Safrole extrinsic. SEQUENCE (SIZE(0..16)) OF TicketEnvelope


@dataclass
class Output(SerializableMixin):
    ok: Optional[OutputMarks] = None  # Markers
    err: Optional[CustomErrorCode] = None  # Error code (not specified in the Graypaper)

    @classmethod
    def scale_type_def(cls):

        return ScaleEnum(
            ok=Option(OutputMarks.scale_type_def()),
            err=CustomErrorCode.scale_type_def()
            # err=Option(ScaleEnum(**{status.name: None for status in CustomErrorCode}))
        )

    def to_scale_type(self) -> ScaleType:
        scale_type = self.scale_type_def().new()
        scale_type.deserialize(self.serialize())
        return scale_type

    @classmethod
    def deserialize(cls: Type[T], data: Union[str, int, float, bool, dict, list]) -> T:

        # # Because of Enum, remove if Err is None
        # if data['err'] is None:
        #     del data['err']

        return super().deserialize(data)

    def serialize(self) -> Union[str, int, float, bool, dict, list]:
        if self.err is not None:
            return {'err': self.err.serialize()}
        else:
            return {'ok': self.ok.serialize()}

