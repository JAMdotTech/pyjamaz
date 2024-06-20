from scalecodec.types import Struct, Vec, H256
from models.block.extrinsic import Extrinsic
from models.state.state_authorizer_queue import StateAuthorizerQueue


class StateAuthorizerPool(Struct):
    #GP-reference: ALPHA | SCALETYPE-DEFINITION: "AUTHORIZER_POOL"->"VEC<AUTHORIZER>" | "AUTHORIZER"->"VEC<AUTHORIZATION>" | "AUTHORIZATION"->"H256"
    #TODO: create separate classes for authorizer_pool and authorizer (used by both StateAuthorizerPool and StateAuthorizerQueue)
    #GP-equation: 82
    arguments = {
        'authorizer_pool': Vec(Vec(H256))
        #TODO Constant(C): CORES=341; size of list is exactly CORES=341 Needs to be more strict. Possible Array(Vec(H256),341)
        #TODO Constant(O): SIZE_AUTHORIZERS_POOL=8; size of list is max (probably, but check) SIZE_AUTHORIZERS_POOL=8 Needs to be more strict. Not possible Array(H256,8)
    }

    #GP-equation: 29,83,84
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.reports]
    #[TODO: input 2: StateAuthorizerQueue of transitioned state]
    #[TODO: input 3: StateAuthorizerPool of current state]
    def state_transition(extrinsic: Extrinsic, state_authorizer_queue: StateAuthorizerQueue, self):
        #[TODO: output 1: self of transitioned state]
        pass

    # GP-equation: 281,(C1)
    def storage_serialize(self):
        #TODO: serialize(self)
        #TODO ATTENTION: ordering is required per GP-equation: 281
        pass

    #TODO: Generalize by introducing the StateKeyConstructor function (C) | GP-reference 280
    def storage_persist(self):
        #TODO: insert/update_kvdb(key:blake2b(0x01|1),value:serialize(self))
        pass

    def storage_get(self):
        #TODO: set self = select_kvdb(key:blake2b(0x01|1))
        pass

