from scalecodec.base import ScaleType
from scalecodec.types import Struct, Vec, H256, U32

from models.common import WorkReport
from models.state.timeslot import Timeslot
from models.state.validator_pool import ValidatorPool


class AssuranceObject(ScaleType):
    def test(self):
        pass


class Assurance(Struct):
    # GP-ref:109
    scale_type_cls = AssuranceObject
    arguments = {
        'work_report': WorkReport(), # GP-ref:109,W
        # TODO: check how many guarantors are allowed
        'guarantors': Vec(H256), # GP-ref:109,g
        'timeslot': U32 # GP-ref:109,t
    }


class AssurancesObject(ScaleType):
    """
    Creates a new `Assurances` object. Assurances is an isolated subsection of State.
    GP-ref: 25
    """
    # GP-ref:25
    # NOTES: this function is a first intermediate step and creates output that is used in GP-ref:26
    def state_transition_judgements(self, extrinsic_judgements: Vec):
        # TODO: input 1: Assurances of current state (self)
        # TODO: input 2: Block.Extrinsic.judgements
        # TODO: output 1: self of first intermediate state
        pass


    # GP-ref:26
    # NOTES: this function is a second intermediate step and creates output that is used in GP-ref:27
    # TODO: check inconsistency if this deals with assurances or guarantees; GP-ref:I.4.2 states guarantees whereas GP-ref:26 states assurances
    # def state_transition_guarantees(extrinsic: Extrinsic, self):
    def state_transition_assurances(self, extrinsic_assurances: Vec):
        # TODO: input 1: Assurances of first intermediate state of # GP-ref:25
        # TODO: input 2: Block.Extrinsic.assurances
        # TODO: output 1: self of second intermediate state
        pass


    # GP-ref:27
    def state_transition(self, extrinsic_guarantees: Vec, validator_pool: ValidatorPool, timeslot: Timeslot):
        # TODO: input 1: Assurances of second intermediate state of # GP-ref:26
        # TODO: input 2: Block.Extrinsic.guarantees
        # TODO: input 3: ValidatorPool of current state
        # TODO: input 4: Timeslot of transitioned state
        # TODO: output 1: self of transitioned state
        pass


   # TODO: with Arjan get/serialize/deserialize this subsection of the state
    def storage_serialize(self):
        # TODO: Generalize by introducing the StateKeyConstructor function (C) | # GP-ref:280
        # TODO: key: blake2b(0x0A|10) # GP-ref: 281,(C10)
        # TODO: value: [define how to serialize] # GP-ref:281,(C10)
        pass

    def storage_persist(self):
        # TODO: insert/update_kvdb(key: blake2b(0x0A | 10), value: serialize(self))
        pass

    def storage_get(self):
        # TODO: set self = select_kvdb(key: blake2b(0x0A | 10))
        pass


class Assurances(Struct):
    # GP-ref:RHO,109
    scale_type_cls = AssurancesObject
    arguments = {
        # TODO: check how many Assurances are allowed
        'assurances': Vec(Assurance())
    }
