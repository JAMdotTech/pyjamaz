from dataclasses import dataclass, field
from typing import Optional

from jamcodec.mixins import Serializable
from jamcodec.types import H256, U64, Array, U8, U32, Null, Vec, Bytes, Option


@dataclass
class CreateServiceInstruction(Serializable):
    # Hash of the code of the new service.
    code_hash: bytes = field(metadata={'codec': H256})
    # Length of the code of the new service.
    code_len: int = field(metadata={'codec': U64})
    # Minimum gas required for each work-item to be accumulated.
    min_item_gas: int = field(metadata={'codec': U64})
    # Minimum gas required for each incoming transfer.
    min_memo_gas: int = field(metadata={'codec': U64})
    # The balance to be transferred to the new service.
    endowment: int = field(metadata={'codec': U64})
    # The memo to be attached to the transfer.
    memo: bytes = field(metadata={'codec': Array(U8, 128)})
    registration: Optional[bytes] = field(metadata={'codec': Option(Bytes)})


@dataclass
class UpgradeInstruction(Serializable):
    # Hash of the code to be upgraded. This must already be in the service's preimage store.
    code_hash: bytes = field(metadata={'codec': H256})
    # Minimum gas required for each work-item to be accumulated.
    min_item_gas: int = field(metadata={'codec': U64})
    # Minimum gas required for each incoming transfer.
    min_memo_gas: int = field(metadata={'codec': U64})


@dataclass
class TransferInstruction(Serializable):
    # The destination service.
    destination: int = field(metadata={'codec': U32})
    # The amount to be transferred.
    amount: int = field(metadata={'codec': U64})
    # The amount of gas for the processing of the transfer by the destination service.
    gas_limit: int = field(metadata={'codec': U64})
    # The memo to give the destination service for the transfer.
    memo: bytes = field(metadata={'codec': Array(U8, 128)})


@dataclass
class ZombifyInstruction(Serializable):
    # The service which will be able to eject the zombie.
    ejector: int = field(metadata={'codec': U32})


@dataclass
class EjectInstruction(Serializable):
    # The target service. This must have empty storage and exactly one preimage
    target: int = field(metadata={'codec': U32})
    # The code hash of the target service, which should be unrequested and droppable.
    code_hash: bytes = field(metadata={'codec': H256})


@dataclass
class DeleteItemsInstruction(Serializable):
    storage_items: list[bytes] = field(metadata={'codec': Vec(Bytes)})


@dataclass
class RandomStorageRefineInstruction(Serializable):
    seed: int = field(metadata={'codec': U64})
    nb_items: int = field(metadata={'codec': U8})


@dataclass
class ExportInstruction(Serializable):
    data: list[bytes] = field(metadata={'codec': Vec(Bytes)})


@dataclass
class SolicitInstruction(Serializable):
    hash: int = field(metadata={'codec': H256})
    len: int = field(metadata={'codec': U64})


@dataclass
class Instruction(Serializable):

    CreateService: CreateServiceInstruction = field(default=None, metadata={'codec': CreateServiceInstruction.to_codec_def()})
    Upgrade: UpgradeInstruction = field(default=None, metadata={'codec': UpgradeInstruction.to_codec_def()})
    Transfer: TransferInstruction = field(default=None, metadata={'codec': TransferInstruction.to_codec_def()})
    Zombify: ZombifyInstruction = field(default=None, metadata={'codec': ZombifyInstruction.to_codec_def()})
    Eject: EjectInstruction = field(default=None, metadata={'codec': EjectInstruction.to_codec_def()})
    DeleteItems: None = field(default=None, metadata={'codec': Null})
    Solicit: SolicitInstruction = field(default=None, metadata={'codec': SolicitInstruction.to_codec_def()})
    Forget: None = field(default=None, metadata={'codec': Null})
    Lookup: None = field(default=None, metadata={'codec': Null})
    Import: None = field(default=None, metadata={'codec': Null})
    Export: ExportInstruction = field(default=None, metadata={'codec': ExportInstruction.to_codec_def()})
    Bless: None = field(default=None, metadata={'codec': Null})
    Assign: None = field(default=None, metadata={'codec': Null})
    Designate: None = field(default=None, metadata={'codec': Null})
    Yield: None = field(default=None, metadata={'codec': Null})
    Checkpoint: None = field(default=None, metadata={'codec': Null})
    Panic: None = field(default=None, metadata={'codec': Null})
    LookedUp: None = field(default=None, metadata={'codec': Null})
    Imported: None = field(default=None, metadata={'codec': Null})
    Exported: None = field(default=None, metadata={'codec': Null})
    RandomStorageRefine: RandomStorageRefineInstruction = field(default=None, metadata={'codec': RandomStorageRefineInstruction.to_codec_def()})

    _codec_enum = True
