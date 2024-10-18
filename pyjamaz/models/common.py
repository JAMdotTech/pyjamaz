from dataclasses import dataclass, field
from typing import List

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
    """
    GP-0.3.8-eq:52 (blackboard_K, blackboard_Y_336) | Collection of validator keys and metadata.

    Attributes
    ----------

    bandersnatch: H256
        GP-0.3.8-eq:53 (k_b | blackboard_H_B) | A validator's Bandersnatch key.
    ed25519: H256
        GP-0.3.8-eq:54 (k_e | blackboard_H_E) | A validator's Edwards 25519 key.
    bls: H256
        GP-0.3.8-eq:55 (k_BLS | blackboard_Y_BLS) | A validator's BLS key.
    metadata: H256
        GP-0.3.8-eq:56 (k_m | blackboard_Y_128) | Metadata for arbitrary data storage.
    """
    # Todo: check consistency with other dataclass definitions, why use: BandersnatchKey
    bandersnatch: BandersnatchKey = field(metadata={'codec': H256})
    # Todo: check consistency with other dataclass definitions, why use: Ed25519Key
    ed25519: Ed25519Key = field(metadata={'codec': H256})
    # Todo: check consistency with other dataclass definitions, why use: BlsKey
    bls: BlsKey = field(metadata={'codec': Array(U8, 144)})
    metadata: ByteArray128 = field(metadata={'codec': Array(U8, 128)})


# Todo: check consistency with other dataclass definitions
ValidatorsData = List[ValidatorData]  # SEQUENCE (SIZE(validators-count)) OF ValidatorData
