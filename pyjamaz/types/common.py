from dataclasses import dataclass, field
from typing import List, Optional

from pyjamaz.serialization import Serializable

U8 = int  # INTEGER (0..255)
U32 = int  # INTEGER (0..4294967295)
ByteArray32 = bytes  # SEQUENCE (SIZE(32)) OF U8
ByteArray128 = bytes
ByteArray144 = bytes
ByteArray784 = bytes
H256 = bytes
OpaqueHash = ByteArray32
Ed25519Key = ByteArray32
BlsKey = ByteArray144  # SEQUENCE (SIZE(144)) OF U8
BandersnatchKey = ByteArray32
EpochKeys = List[BandersnatchKey]  # SEQUENCE (SIZE(epoch-length)) OF BandersnatchKey


@dataclass
class ValidatorData(Serializable):
    bandersnatch: BandersnatchKey = field(metadata={'length': 32})
    ed25519: Ed25519Key = field(metadata={'length': 32})
    bls: BlsKey = field(metadata={'length': 144})
    metadata: ByteArray128 = field(metadata={'length': 128})


ValidatorsData = List[ValidatorData]  # SEQUENCE (SIZE(validators-count)) OF ValidatorData


@dataclass
class Mmr(Serializable):
    peaks: List[H256] = field(default_factory=list)


@dataclass
class BlockInfo(Serializable):
    header_hash: H256
    mmr: Mmr
    state_root: H256
    reported: List[H256] = field(default_factory=list)
