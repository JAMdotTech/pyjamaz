from scalecodec.types import Struct, Vec, H256
from models.block.extrinsic import Extrinsic
from models.state.state_authorizer_queue import StateAuthorizerQueue


class StateAuthorizerPool(Struct):
    #GP-reference: ALPHA | SCALETYPE-DEFINITION: "AUTHORIZER_POOL"->"VEC<AUTHORIZER>" | "AUTHORIZER"->"VEC<AUTHORIZATION>" | "AUTHORIZATION"->"H256" |
    #GP-equation: 82
    arguments = {
        'state': Vec(Vec(H256))
    }

    #GP-equation: 29,83,84
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.reports]
    #[TODO: input 2: StateAuthorizerQueue of transitioned state]
    #[TODO: input 3: StateAuthorizerPool of current state]
    def state_transition(extrinsic: Extrinsic, state_authorizer_queue: StateAuthorizerQueue, self):
        #[TODO: output 1: self of transitioned state]
        pass
