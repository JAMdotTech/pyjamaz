from dataclasses import dataclass, field
from typing import List, Optional

from jamcodec.mixins import Serializable
from jamcodec.types import H256, Array, U8

ByteArray32 = bytes  # SEQUENCE (SIZE(32)) OF U8
ByteArray128 = bytes
ByteArray144 = bytes
ByteArray784 = bytes
OpaqueHash = ByteArray32
Ed25519Key = ByteArray32
BlsKey = ByteArray144  # SEQUENCE (SIZE(144)) OF U8
BandersnatchKey = ByteArray32
EpochKeys = List[BandersnatchKey]  # SEQUENCE (SIZE(epoch-length)) OF BandersnatchKey


@dataclass
class ValidatorData(Serializable):
    bandersnatch: BandersnatchKey = field(metadata={'codec': H256})
    ed25519: Ed25519Key = field(metadata={'codec': H256})
    bls: BlsKey = field(metadata={'codec': Array(U8, 144)})
    metadata: ByteArray128 = field(metadata={'codec': Array(U8, 128)})


ValidatorsData = List[ValidatorData]  # SEQUENCE (SIZE(validators-count)) OF ValidatorData
