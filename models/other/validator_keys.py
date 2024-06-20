from scalecodec.types import Struct, H256, U8, Array


class ValidatorKeys(Struct):
    #GP-equation: 50 | SCALETYPE-DEFINITION: "ValidatorKeys"->"(BS_KEY,ED25519_KEY,BLS_KEY,METADATA)" | "BS_KEY"->"H256" | "ED25519_KEY"->"H256" | "BLS_KEY"->"H1152" | "METADATA"->"H1024"
    arguments = {
        'bs_key': H256,
        'ed25519_key': H256,
        'bls_key': Array(U8,144),
        'metadata': Array(U8,128)
    }

