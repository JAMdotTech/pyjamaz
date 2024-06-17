from scalecodec.types import Struct, Vec, Tuple, H256, Option
from models.header import Header


class StateRecentBlocks(Struct):
    #GP-reference: BETA | SCALETYPE-DEFINITION: "RECENT_BLOCKS"->"VEC<RECENT_BLOCK>" | "RECENT_BLOCK"->"(HEADER_HASH,ACCUMULATION_RESULTS,STATE_ROOT,WORK_REPORTS)" | "ACCUMULATION_RESULTS"->"OPTION<ACCUMULATION_RESULT>" | "ACCUMULATION_RESULT"->"H256" | "STATE_ROOT"->"H256" | "WORK_REPORTS"->"VEC<WORK_REPORT_HASH>" | "WORK_REPORT_HASH"->"H256"
    arguments = {
        'recent_blocks': Vec(Tuple(H256,Vec(Option(H256)),H256,Vec(H256)))
    }

    #graypaper-equation: 18
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: Block.Extrinsic.reports]
    #[TODO: input 3: State.recent_blocks of intermediate state (result of graypaper-equation 17]
    #[TODO: input 4: 'C'-object to be determined Beefy related ]
    def state_transition(header: Header, i2: {}, i3: {}, i4: {}):
        #[TODO: output 1: self of transitioned state]
        pass

