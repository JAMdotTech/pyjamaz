from scalecodec.base import ScaleType
from scalecodec.types import Struct, Vec, H256
from models.block import Extrinsic
from models.old_state.state_authorizer_queue import StateAuthorizerQueue


class StateAuthorizerPoolObject(ScaleType):
    def state_transition(extrinsic: Extrinsic, state_authorizer_queue: StateAuthorizerQueue, self):
        # GP-ref:29,83,84
        # Todo: Volgorde input parameters SELF eerst conventie?
        # TODO: input 1: Block.Extrinsic.reports
        # TODO: input 2: StateAuthorizerQueue of transitioned state
        # TODO: input 3: StateAuthorizerPool of current state
        # TODO: output 1: self of transitioned state
        pass

    def storage_serialize(self):
        # TODO: Generalize by introducing the StateKeyConstructor function (C) | GP-ref 280
        # TODO: serialize(self) | following specific definition GP-ref:281,(C1)
        pass

    def storage_persist(self):
        # TODO: insert/update_kvdb(key: blake2b(0x01|1), value: serialize(self))
        pass

    def storage_get(self):
        # TODO: set self = select_kvdb(key: blake2b(0x01|1))
        pass



class StateAuthorizerPool(Struct):
    #GP-ref: ALPHA,82 | SCALETYPE-DEFINITION: "AUTHORIZER_POOL"->"VEC<AUTHORIZER>" | "AUTHORIZER"->"VEC<AUTHORIZATION>" | "AUTHORIZATION"->"H256"
    #TODO: create separate classes for authorizer_pool and authorizer (used by both StateAuthorizerPool and StateAuthorizerQueue)
    arguments = {
        'authorizer_pool': Vec(Vec(H256))
        #TODO Constant(C): CORES=341; size of list is exactly CORES=341 Needs to be more strict. Possible Array(Vec(H256),341)
        #TODO Constant(O): SIZE_AUTHORIZERS_POOL=8; size of list is max (probably, but check) SIZE_AUTHORIZERS_POOL=8 Needs to be more strict. Not possible Array(H256,8)
    }

