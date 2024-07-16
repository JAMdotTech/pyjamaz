from scalecodec.base import ScaleType
from scalecodec.types import Struct, Vec, H256

from pyjamaz.models.state.authorizer_queue import AuthorizerQueue


class AuthorizerPoolObject(ScaleType):
    """
    Creates a new `AuthorizerQueue` object. AuthorizerQueue is an isolated subsection of State.
    GP-ref: 28,83,84
    """
    def state_transition(self, extrinsic_guarantees: Vec, authorizer_queue: AuthorizerQueue):
        # GP-ref:29,83,84
        # TODO: input 1: AuthorizerPool of current state (self)
        # TODO: input 2: Block.Extrinsic.guarantees
        # TODO: input 3: AuthorizerQueue of transitioned state
        # TODO: output 1: self of transitioned state
        pass

    def storage_serialize(self):
        # TODO: Generalize by introducing the StateKeyConstructor function (C) | # GP-ref:280
        # TODO: serialize(self) | following specific definition GP-ref:281,(C1)
        pass

    def storage_persist(self):
        # TODO: insert/update_kvdb(key: blake2b(0x01|1), value: serialize(self))
        pass

    def storage_get(self):
        # TODO: set self = select_kvdb(key: blake2b(0x01|1))
        pass


class AuthorizerPool(Struct):
    #GP-ref:ALPHA,82
    # TODO: create separate classes for authorizer_pool and authorizer (used by both AuthorizerPool and AuthorizerQueue)
    scale_type_cls = AuthorizerPoolObject
    arguments = {
        #TODO Constant(C): CORES=341; size of list is exactly CORES=341 Needs to be more strict. Possible Array(Vec(H256),341)
        #TODO Constant(O): SIZE_AUTHORIZERS_POOL=8; size of list is max (probably, but check) SIZE_AUTHORIZERS_POOL=8 Needs to be more strict. Not possible Array(H256,8)
        'authorizer_pool': Vec(Vec(H256))
    }
