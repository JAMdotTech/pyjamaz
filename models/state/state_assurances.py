from scalecodec.types import Struct, Vec
from models.other.assurance import Assurance
from models.block.extrinsic import Extrinsic
from models.state.state_timeslot import StateTimeslot
from models.state.state_validator_pool import StateValidatorPool


class StateAssurances(Struct):
    #GP-reference: RHO | SCALETYPE-DEFINITION: "ASSURANCES"->"VEC<ASSURANCE>" -> refer to class Assurance for details.
    #GP-equation: 109
    arguments = {
        'assurances': Vec(Assurance())
    }

    #GP-equation: 25
    #[NOTES: this function is a first intermediate step and creates output that is used in graypaper-equation: 26]
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.judgements]
    #[TODO: input 2: StateAssurances of current state]
    def state_transition_judgements(extrinsic: Extrinsic, self):
        #[TODO: output 1: self of first intermediate state]
        pass


    #GP-equation: 26
    #[NOTES: this function is a second intermediate step and creates output that is used in GP-equation: 27]
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.assurances]
    #[TODO: input 2: StateAssurances of first intermediate state of GP-equation: 25]
    #[TODO: check inconsistency if this deals with assurances or guarantees; GP-I.4.2 states guarantees whereas GP-equation 26 states assurances]
    #def state_transition_guarantees(extrinsic: Extrinsic, self):
    def state_transition_assurances(extrinsic: Extrinsic, self):

        #[TODO: output 1: self of second intermediate state]
        pass


    #GP-equation: 27
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.reports]
    #[TODO: input 2: StateAssurances of second intermediate state of GP-equation: 26]
    #[TODO: input 3: StateValidatorPool of current state]
    #[TODO: input 4: Timeslot of transitioned state]
    def state_transition(extrinsic: Extrinsic, self, state_validator_pool: StateValidatorPool, state_timeslot: StateTimeslot):
        #[TODO: output 1: self of transitioned state]
        pass

