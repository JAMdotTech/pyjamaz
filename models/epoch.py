from scalecodec.types import Struct, H256, Vec


class Epoch(Struct):
    #GP-reference: 43,69 | SCALETYPE-DEFINITION: "EPOCH"->"OPTION<(ENTROPY,BS_KEYS)>" | "ENTROPY"->"H256" | "BS_KEYS"->"VEC<BS_KEY>" | "BS_KEY"->"H256"
    #GP-equation: 43,69
    arguments = {
        'entropy': H256,
        'bs_keys': Vec(H256)
    }

