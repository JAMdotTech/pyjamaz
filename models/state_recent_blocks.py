from scalecodec.types import Struct, Vec, Tuple, H256, Option
from models.header import Header
from models.extrinsic import Extrinsic


class StateRecentBlocks(Struct):
    #GP-reference: BETA | SCALETYPE-DEFINITION: "RECENT_BLOCKS"->"VEC<RECENT_BLOCK>" | "RECENT_BLOCK"->"(HEADER_HASH,ACCUMULATION_RESULTS,STATE_ROOT,WORK_REPORTS)" | "ACCUMULATION_RESULTS"->"OPTION<ACCUMULATION_RESULT>" | "ACCUMULATION_RESULT"->"H256" | "STATE_ROOT"->"H256" | "WORK_REPORTS"->"VEC<WORK_REPORT_HASH>" | "WORK_REPORT_HASH"->"H256"
    arguments = {
        'state': Vec(Tuple(H256,Vec(Option(H256)),H256,Vec(H256)))
    }

    #GP-equation: 17
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: StateRecentBlocks of current state]
    def state_transition_intermediate(header: Header, self):
        #[TODO: output 1: self of intermediate state]
        pass

    #GP-equation: 18
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: Block.Extrinsic.reports]
    #[TODO: input 3: StateRecentBlocks of intermediate state (result of graypaper-equation 17]
    #[TODO: input 4: 'C'-object to be determined Beefy related ]
    def state_transition(header: Header, extrinsic: Extrinsic, self, i4: {}):
        #[TODO: output 1: self of transitioned state]
        pass

