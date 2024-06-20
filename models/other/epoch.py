from scalecodec.types import Struct, H256, Vec


class Epoch(Struct):
    #GP-equation: 43,69 | SCALETYPE-DEFINITION: "EPOCH"->"OPTION<(ENTROPY,BS_KEYS)>"
    #GP-reference: ETA-1 | SCALETYPE-DEFINITION: "ENTROPY"->"H256"
    #GP-reference: k | SCALETYPE-DEFINITION: "BS_KEYS"->"VEC<BS_KEY>" | "BS_KEY"->"H256"
    arguments = {
        'entropy': H256,
        'bs_keys': Vec(H256) #TODO Constant(V): VALIDATORS=1023; size of list is exactly VALIDATORS=1023 Needs to be more strict. Possible Array(H256,1023)
    }

