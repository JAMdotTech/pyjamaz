from scalecodec.types import Struct, H256, U8, Array


class ValidatorKeys(Struct):
    #GP-equation: 50,51,K | SCALETYPE-DEFINITION: "ValidatorKeys"->"(BS_KEY,ED25519_KEY,BLS_KEY,METADATA)"
    #GP-reference: 52,vb | SCALETYPE-DEFINITION: "BS_KEY"->"H256"
    #GP-reference: 53,ve | SCALETYPE-DEFINITION: "ED25519_KEY"->"H256"
    #GP-reference: 54,vBLS | SCALETYPE-DEFINITION: "BLS_KEY"->"H1152"
    #GP-reference: 55,vm | SCALETYPE-DEFINITION: "METADATA"->"H1024"
    arguments = {
        'bs_key': H256,
        'ed25519_key': H256,
        'bls_key': Array(U8,144),
        'metadata': Array(U8,128)
    }

