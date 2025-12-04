from dataclasses import dataclass, field
from typing import Optional, List, Tuple

from jamcodec.mixins import Serializable
from jamcodec.types import H256, U64, Array, U8, Option, Bytes, U32, Vec, Null, Tuple as JamTuple, Bool, U16
from pyjamaz.graypaper_constants import MAXIMUM_AUTHORIZATION_QUEUE_ITEMS, VALIDATOR_COUNT
from pyjamaz.models.common import ValidatorData


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
class ImportInstruction(Serializable):
    items: list[Tuple[int, int]] = field(metadata={'codec': Vec(JamTuple(U64, U64))})


@dataclass
class ExportInstruction(Serializable):
    data: list[bytes] = field(metadata={'codec': Vec(Bytes)})


@dataclass
class SolicitInstruction(Serializable):
    hash: int = field(metadata={'codec': H256})
    len: int = field(metadata={'codec': U64})


@dataclass
class ForgetInstruction(Serializable):
    hash: int = field(metadata={'codec': H256})
    len: int = field(metadata={'codec': U64})


@dataclass
class LookupInstruction(Serializable):
    service: int = field(metadata={'codec': U32})
    hash: int = field(metadata={'codec': H256})
    eager: bool = field(metadata={'codec': Bool})


@dataclass
class BlessInstruction(Serializable):
    manager: int = field(metadata={'codec': U32})
    assign: int = field(metadata={'codec': U32})
    designate: int = field(metadata={'codec': U32})
    register: int = field(metadata={'codec': U32})
    auto_acc: List[Tuple[int, int]] = field(metadata={'codec': Vec(JamTuple(U32, U64))})


@dataclass
class AssignInstruction(Serializable):
    core: int = field(metadata={'codec': U16})
    queue: List[bytes] = field(metadata={'codec': Array(H256, MAXIMUM_AUTHORIZATION_QUEUE_ITEMS)})
    assigner: int = field(metadata={'codec': U32})


@dataclass
class DesignateInstruction(Serializable):
    keys: list[ValidatorData] = field(metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)})


@dataclass
class YieldInstruction(Serializable):
    hash: bytes = field(metadata={'codec': H256})


@dataclass
class ProvideInstruction(Serializable):
    service_id: int = field(metadata={'codec': U32})
    preimage: bytes = field(metadata={'codec': H256})


@dataclass
class Instruction(Serializable):

    CreateService: CreateServiceInstruction = field(default=None, metadata={'codec': CreateServiceInstruction.to_codec_def()})
    Upgrade: UpgradeInstruction = field(default=None, metadata={'codec': UpgradeInstruction.to_codec_def()})
    Transfer: TransferInstruction = field(default=None, metadata={'codec': TransferInstruction.to_codec_def()})
    Zombify: ZombifyInstruction = field(default=None, metadata={'codec': ZombifyInstruction.to_codec_def()})
    Eject: EjectInstruction = field(default=None, metadata={'codec': EjectInstruction.to_codec_def()})
    DeleteItems: DeleteItemsInstruction = field(default=None, metadata={'codec': DeleteItemsInstruction.to_codec_def()})
    Solicit: SolicitInstruction = field(default=None, metadata={'codec': SolicitInstruction.to_codec_def()})
    Forget: ForgetInstruction = field(default=None, metadata={'codec': ForgetInstruction.to_codec_def()})
    Lookup: LookupInstruction = field(default=None, metadata={'codec': LookupInstruction.to_codec_def()})
    Import: ImportInstruction = field(default=None, metadata={'codec': ImportInstruction.to_codec_def()})
    Export: ExportInstruction = field(default=None, metadata={'codec': ExportInstruction.to_codec_def()})
    Bless: BlessInstruction = field(default=None, metadata={'codec': BlessInstruction.to_codec_def()})
    Assign: AssignInstruction = field(default=None, metadata={'codec': AssignInstruction.to_codec_def()})
    Designate: DesignateInstruction = field(default=None, metadata={'codec': DesignateInstruction.to_codec_def()})
    Yield: YieldInstruction = field(default=None, metadata={'codec': YieldInstruction.to_codec_def()})
    Checkpoint: None = field(default=None, metadata={'codec': Null})
    Panic: None = field(default=None, metadata={'codec': Null})
    Provide: ProvideInstruction = field(default=None, metadata={'codec': ProvideInstruction.to_codec_def()})
    LookedUp: None = field(default=None, metadata={'codec': Null})
    Imported: None = field(default=None, metadata={'codec': Null})
    Exported: None = field(default=None, metadata={'codec': Null})
    RandomStorageRefine: RandomStorageRefineInstruction = field(default=None, metadata={'codec': RandomStorageRefineInstruction.to_codec_def()})
    RandomStorageAccumulate: None = field(default=None, metadata={'codec': Null})
    Benchmark: None = field(default=None, metadata={'codec': Null})

    _codec_enum = True


@dataclass
class ServiceInfo(Serializable):
    id: int = field(metadata={'codec': U32})
    code_hash: bytes = field(metadata={'codec': H256})


@dataclass
class ServiceRegistry(Serializable):
    services: List[Tuple[bytes, ServiceInfo]] = field(metadata={'codec': Vec(JamTuple(Bytes, ServiceInfo.to_codec_def()))})
