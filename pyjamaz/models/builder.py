from dataclasses import dataclass, field

from jamcodec.mixins import Serializable
from jamcodec.types import H256, U64, Array, U8


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

@dataclass
class Instruction(Serializable):
    CreateService: CreateServiceInstruction = field(metadata={'codec': CreateServiceInstruction.to_codec_def()})
    _codec_enum = True
