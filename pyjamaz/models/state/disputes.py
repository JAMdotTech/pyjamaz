from scalecodec.base import ScaleType
from scalecodec.types import Struct, Vec, H256

from pyjamaz.models.common import ValidatorKeys


class DisputesObject(ScaleType):
    """
    Creates a new `Disputes` object. Disputes is an isolated subsection of State.
    GP-ref: 23
    """
    # GP-ref:23
    def state_transition(self, extrinsic_judgements: Vec):
        # TODO: input 1: Disputes of current state (self)
        # TODO: input 2: Block.Extrinsic.judgements
        # TODO: output 1: self of transitioned state
        pass

   # TODO: with Arjan get/serialize/deserialize this subsection of the state
    def storage_serialize(self):
        # TODO: Generalize by introducing the StateKeyConstructor function (C) | # GP-ref:280
        # TODO: key: blake2b(0x05|5) # GP-ref: 281,(C5)
        # TODO: value: [define how to serialize] # GP-ref:281,(C5)
        pass

    def storage_persist(self):
        # TODO: insert/update_kvdb(key: blake2b(0x05|5), value: serialize(self))
        pass

    def storage_get(self):
        # TODO: set self = select_kvdb(key: blake2b(0x05|5))
        pass


class Disputes(Struct):
    # GP-ref:PSI,94
    scale_type_cls = DisputesObject
    arguments = {
        # TODO: check how many allowed?
        'allow_set': Vec(H256), # GP-ref:94,PSI-a
        # TODO: check how many allowed?
        'ban_set': Vec(H256), # GP-ref:94,PSI-b
        # TODO: check how many allowed?
        'punish_set': Vec(H256), # GP-ref:94,PSI-p
        # TODO Constant(V): VALIDATORS=1023; size of list is exactly VALIDATORS=1023 Needs to be more strict. Possible Array(ValidatorKeys(),1023)
        'validators_prior_epoch': Vec(ValidatorKeys()) # GP-ref:94,PSI-k,50
    }
