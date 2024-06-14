from models import Header

class StateRecentBlocks:
    #graypaper-reference: BETA
    def __init__(self):
        #definition
        self = [{},{},{},{},{},{},{},{}]

    #graypaper-equation: 17
    #[NOTES: this function is an intermediate step and creates output that is used in graypaper-equation: 18]
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: State.recent_blocks of current state]
    def state_transition_intermediate1(header: Header, self):
        #[TODO: output 1: self of intermediate state]
        pass

    #graypaper-equation: 18
    #[NOTE: how can we more explicitly follow GP by only having 'beta' instead of self as input (subset of state)]
    #[NOTE: how can we more explicitly follow GP by only having 'Extrinsic.reports' as input (subset of extrinsic)]
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: Block.Extrinsic.reports]
    #[TODO: input 3: State.recent_blocks of intermediate state (result of graypaper-equation 17]
    #[TODO: input 4: 'C'-object to be determined Beefy related ]
    def state_transition(header: Header, i2: {}, i3: {}, i4: {}):
        #[TODO: output 1: self of transitioned state]
        pass


