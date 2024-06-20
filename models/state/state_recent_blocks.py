from scalecodec.types import Struct, Array
from models.block.header import Header
from models.block.extrinsic import Extrinsic
from models.other.recent_block import RecentBlock


class StateRecentBlocks(Struct):
    #GP-reference: BETA | SCALETYPE-DEFINITION: "RECENT_BLOCKS"->"VEC<RECENT_BLOCK>" | "RECENT_BLOCK"-> refer to class RecentBlock for details.
    #GP-equation: 79
    arguments = {
        'recent_blocks': Array(RecentBlock(),8)
    }

    #GP-equation: 17
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: StateRecentBlocks of current state]
    def state_transition_intermediate(header: Header, self):
        #[TODO: output 1: self of intermediate state]
        pass

    #GP-equation: 18,80,81
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: Block.Extrinsic.reports]
    #[TODO: input 3: StateRecentBlocks of intermediate state (result of graypaper-equation 17]
    #[TODO: input 4: 'C'-object to be determined Beefy related ]
    def state_transition(header: Header, extrinsic: Extrinsic, self, i4: {}):
        #[TODO: output 1: self of transitioned state]
        pass

