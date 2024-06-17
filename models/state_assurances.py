from scalecodec.types import Struct, Tuple, Vec, H256, U32
from models.work_report import WorkReport


class StateAssurances(Struct):
    #GP-reference: RHO | SCALETYPE-DEFINITION: "ASSURANCES"->"VEC<ASSURANCE>" | "ASSURANCE"->"(WORK_REPORT,GUARANTORS,TIMESLOT)" | "WORK_REPORT"-> refer to class WorkReport for details. | "GUARANTORS"->"VEC<GUARANTOR>" | "TIMESLOT"->"U32"
    arguments = {
        'assurances': Vec(Tuple(WorkReport(),Vec(H256),U32))
    }

    #GP-equation: 21
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: Timeslot of current state]
    #[TODO: input 3: State.validator_pool of current state]
    #[TODO: input 4: State.safrole of current state]
    #[TODO: input 5: State.disputes of transitioned state]
    #graypaper-equation: 25
    #[NOTES: this function is a first intermediate step and creates output that is used in graypaper-equation: 26]
    #[TODO: input 1: Block.Extrinsic.judgements]
    #[TODO: input 2: State.assurances of current state]
    def state_transition_intermediate1(i1: {}, i2: {}):
        #[TODO: output 1: self of first intermediate state]
        pass


    #graypaper-equation: 26
    #[NOTES: this function is a second intermediate step and creates output that is used in graypaper-equation: 27]
    #[TODO: input 1: Block.Extrinsic.assurances]
    #[TODO: input 2: State.assurances of first intermediate state of graypaper-equation: 25]
    def state_transition_intermediate2(i1: {}, i2: {}):
        #[TODO: output 1: self of second intermediate state]
        pass


    #graypaper-equation: 27
    #[TODO: input 1: Block.Extrinsic.reports]
    #[TODO: input 2: State.assurances of second intermediate state of graypaper-equation: 26]
    #[TODO: input 3: State.validators of current state]
    #[TODO: input 4: Timeslot of transitioned state]
    def state_transition(i1: {}, i2: {}, i3: {}, i4: {}):
        #[TODO: output 1: self of transitioned state]
        pass

