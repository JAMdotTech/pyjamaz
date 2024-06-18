from scalecodec.types import Struct, Tuple, Vec, H256, U32
from models.extrinsic import Extrinsic
from models.state_timeslot import StateTimeslot
from models.state_validator_pool import StateValidatorPool
from models.work_report import WorkReport


class StateAssurances(Struct):
    #GP-reference: RHO | SCALETYPE-DEFINITION: "ASSURANCES"->"VEC<ASSURANCE>" | "ASSURANCE"->"(WORK_REPORT,GUARANTORS,TIMESLOT)" | "WORK_REPORT"-> refer to class WorkReport for details. | "GUARANTORS"->"VEC<GUARANTOR>" | "TIMESLOT"->"U32"
    arguments = {
        'state': Vec(Tuple(WorkReport(),Vec(H256),U32))
    }

    #graypaper-equation: 25
    #[NOTES: this function is a first intermediate step and creates output that is used in graypaper-equation: 26]
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.judgements]
    #[TODO: input 2: StateAssurances of current state]
    def state_transition_intermediate1(extrinsic: Extrinsic, self):
        #[TODO: output 1: self of first intermediate state]
        pass


    #graypaper-equation: 26
    #[NOTES: this function is a second intermediate step and creates output that is used in graypaper-equation: 27]
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.assurances]
    #[TODO: input 2: StateAssurances of first intermediate state of graypaper-equation: 25]
    def state_transition_intermediate2(extrinsic: Extrinsic, self):
        #[TODO: output 1: self of second intermediate state]
        pass


    #graypaper-equation: 27
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.reports]
    #[TODO: input 2: StateAssurances of second intermediate state of graypaper-equation: 26]
    #[TODO: input 3: StateValidatorPool of current state]
    #[TODO: input 4: Timeslot of transitioned state]
    def state_transition(extrinsic: Extrinsic, self, state_validator_pool: StateValidatorPool, state_timeslot: StateTimeslot):
        #[TODO: output 1: self of transitioned state]
        pass

