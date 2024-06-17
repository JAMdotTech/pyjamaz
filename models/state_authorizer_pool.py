from scalecodec.types import Struct, Vec, H256

class StateAuthorizerPool(Struct):
    #GP-reference: ALPHA | SCALETYPE-DEFINITION: "AUTHORIZER_POOL"->"VEC<AUTHORIZER>" | "AUTHORIZER"->"VEC<AUTHORIZATION>" | "AUTHORIZATION"->"H256" |
    arguments = {
        'authorizer_pool': Vec(Vec(H256))
    }

    #graypaper-equation: 29
    #[TODO: input 1: Block.Extrinsic.reports]
    #[TODO: input 2: State.authorizers_queue of transitioned state]
    #[TODO: input 3: State.authorizers of current state]
    def state_transition(i1: {}, i2: {}, i3: {}):
        #[TODO: output 1: self of transitioned state]
        pass
