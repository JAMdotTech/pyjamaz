from dataclasses import dataclass, field

from jamcodec.mixins import Serializable
from jamcodec.types import H256, Array, U8


@dataclass
class ValidatorData(Serializable):
    """
    GP-0.5.0-eq:6.7,6.8 (blackboard_K, blackboard_Y_336) | Collection of validator keys and metadata.

    Attributes
    ----------

    bandersnatch: H256
        GP-0.5.0-eq:6.9 (k_b | blackboard_H_B) | A validator's Bandersnatch key.
    ed25519: H256
        GP-0.5.0-eq:6.10 (k_e | blackboard_H_E) | A validator's Edwards 25519 key.
    bls: H256
        GP-0.5.0-eq:6.11 (k_BLS | blackboard_Y_BLS) | A validator's BLS key.
    metadata: H256
        GP-0.5.0-eq:6.12 (k_m | blackboard_Y_128) | Metadata for arbitrary data storage.
    """
    bandersnatch: bytes = field(metadata={'codec': H256})
    ed25519: bytes = field(metadata={'codec': H256})
    bls: bytes = field(metadata={'codec': Array(U8, 144)})
    metadata: bytes = field(metadata={'codec': Array(U8, 128)})
