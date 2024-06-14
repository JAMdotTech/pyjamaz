from models import Header
from models.header import Header


class Extrinsic:
    #graypaper-equation: 14
    def __init__(self):
        # graypaper-equation: 71
        #SCALETYPE-DEFINITION: "TICKETS"->"VEC<TICKET>" | "TICKET"->"(ENTRY_IDX,VALIDITY_PROOF)" | "ENTRY_IDX"->"U8" | "VALIDITY_PROOF"->"64BYTEHASH"
        #ENCODED: 'HOEGINGDATOOKALWEER'
        #PYTHON: []
        #DECODED-JSON: []
        self.tickets = []

        # graypaper-equation: 96
        #SCALETYPE-DEFINITION: "JUDGEMENTS"->"VEC<JUDGEMENT>" | "JUDGEMENT"->"(WORK_REPORT_HASH,VOTES)" | "WORK_REPORT_HASH"->"32BYTEHASH" | "VOTES"->"VEC<VOTE>" | "VOTE"->"(IS_VALID,VALIDATOR_IDX,SIGNATURE)" | "IS_VALID"->"BOOLEAN" | "VALIDATOR_IDX"->"U16" | "SIGNATURE"->"64BYTEHASH"
        #ENCODED: 'HOEGINGDATOOKALWEER'
        #PYTHON: []
        #DECODED-JSON: []
        self.judgements = []

        # graypaper-equation: 148
        #SCALETYPE-DEFINITION: "PREIMAGES"->"VEC<PREIMAGE>" | "PREIMAGE"->"(SERVICE_IDX,DATA)" | "SERVICE_IDX"->"U32" | "DATA"->"BLOB?"
        #ENCODED: 'HOEGINGDATOOKALWEER'
        #PYTHON: []
        #DECODED-JSON: []
        self.preimages = []

        # graypaper-equation: ???
        #SCALETYPE-DEFINITION: "ASSURANCES"->"VEC<ASSURANCE>" | "ASSURANCE"->"(WORK_REPORT_HASH,IS_AVAILABLE,VALIDATOR_IDX,SIGNATURE)" | "WORK_REPORT_HASH"->"32BYTEHASH" | "IS_AVAILABLE"->"BOOLEAN" | "VALIDATOR_IDX"->"U16" | "SIGNATURE"->"64BYTEHASH"
        #ENCODED: 'HOEGINGDATOOKALWEER'
        #PYTHON: []
        #DECODED-JSON: []
        self.assurances = []

        # graypaper-equation: 130
        #SCALETYPE-DEFINITION: "GUARANTEES"->"VEC<GUARANTEE>" | "GUARANTEE"->"(CORE_IDX,WORK_REPORT,TIMESLOT,CREDENTIAL)" | "CORE_IDX"->"U16" | "WORK_REPORT"->"(AUTHORIZERS_HASH,OUTPUT,REFINEMENT_CONTEXT,WORK_PACKAGE,RESULTS)" | "AUTHORIZERS_HASH"->"32BYTEHASH" | "OUTPUT"->"BLOB" | "REFINEMENT_CONTEXT"->"(ANCHOR_HEADER_HASH,ANCHOR_POSTERIOR_STATE_ROOT,POSTERIOR_BEEFY_ROOT,LOOKUP_ANCHOR_HEADER_HASH,LOOKUP_ANCHOR_TIMESLOT,OPTION<WORK_PACKAGE_HASH>)" | "ANCHOR_HEADER_HASH"->"32BYTEHASH" | "ANCHOR_POSTERIOR_STATE_ROOT"->"32BYTEHASH" | "POSTERIOR_BEEFY_ROOT"->"32BYTEHASH" | "LOOKUP_ANCHOR_HEADER_HASH"->"32BYTEHASH" | "LOOKUP_ANCHOR_TIMESLOT"->"U32" | "WORK_PACKAGE_HASH"->"32BYTEHASH" | "WORK_PACKAGE"->"(WORK_PACKAGE_HASH,WORK_PACKAGE_LENGTH,ERASURE_ROOT,SEGMENT_ROOT)" | "WORK_PACKAGE_HASH"->"32BYTEHASH" | "WORK_PACKAGE_LENGTH"->"U32" | "ERASURE_ROOT"->"32BYTEHASH" | "SEGMENT_ROOT"->"32BYTEHASH" | "RESULTS"->"VEC<RESULT>" | "RESULT"->"(SERVICE_IDX,CODE_HASH,PAYLOAD_HASH,GAS_PRIORIZATION_RATIO,ERROR)" | "SERVICE_IDX"->"U32" | "CODE_HASH"->"32BYTEHASH" | "PAYLOAD_HASH"->"32BYTEHASH" | "GAS_PRIORIZATION_RATIO"->"S64" | "ERROR"->"ENUM<OUT-OF-GAS,UNEXPECTED-TERMINATION,BAD,BIG>" | "TIMESLOT"->"U32" | "CREDENTIAL"->"VEC<OPTION<SIGNATURE>> | "SIGNATURE"->"64BYTEHASH"
        #ENCODED: 'HOEGINGDATOOKALWEER'
        #PYTHON: []
        #DECODED-JSON: []
        self.guarantees = []

        # graypaper-equation: 14
        #DEFINE FUNCTION THAT OUTPUTS SERIALIZED EXTRINSIC(DATA)
        #SCALETYPE-DEFINITION: "EXTRINSIC"->"(TICKETS,JUDGEMENTS,PREIMAGES,AVAILABILITY,REPORTS)"
        #ENCODED: 0x0000000000
        #PYTHON: [TODO]
        #DECODED-JSON: { "tickets": [],
        # "judgements": [],
        # "preimages": [],
        # "availability": [],
        # "reports": []
        # }

        # graypaper-equation: 14
        # DEFINE FUNCTION THAT UNSERIALIZES EXTRINSIC(DATA)

        # graypaper-equation: 39
        # DEFINE FUNCTION THAT HASHES EXTRINSIC(DATA)

        # graypaper-equation: 39
        # DEFINE FUNCTION THAT VERIFIES HASH OF EXTRINSIC(DATA)


class Block:
    #graypaper-equation: 13
    def __init__(self, header: Header, extrinsic: Extrinsic):
        self.header = header
        self.extrinsic = extrinsic

        # graypaper-equation: 13
        # DEFINE FUNCTION THAT SERIALIZES BLOCK(DATA)

        # graypaper-equation: 13
        # DEFINE FUNCTION THAT UNSERIALIZES BLOCK(DATA)


class State:
    #graypaper-equation: 15
    def __init__(self):
        #graypaper-reference: ALPHA
        #[]
        self.authorizers = {} #StateAuthorizers

        #graypaper-reference: BETA
        self.recent_blocks = [{},{},{},{}] #StateRecentBlocks

        #graypaper-reference: GAMMA
        self.safrole = {} #StateSafrole

        #graypaper-reference: DELTA
        self.services = {} #StateServices

        #graypaper-reference: ETA
        self.entropy = {} #StateEntropy

        #graypaper-reference: IOTA
        self.enqueued_validators = {}  #StateEnqueuedValidators

        #graypaper-reference: KAPPA
        self.validators = {} #StateValidators

        #graypaper-reference: LAMBDA
        self.archived_validators = {} #StateArchivedValidators

        #graypaper-reference: RHO
        self.assurances = {} #StateAssurances

        #graypaper-reference: TAU
        self.timeslot = 1 #StateTimeslot

        #graypaper-reference: PHI
        self.authorizers_queue = {} #StateAuthorizersQueue

        #graypaper-reference: CHI
        self.priviliged_services = {} #StatePriviligedServices

        #graypaper-reference: PSI
        self.disputes = {} #StateDisputes

    #graypaper-equation: 12
    #[TODO: input 1: State]
    #[TODO: input 2: Block]
    def state_transition(self, block: Block):
        # specification of state transitions per step
        # 14 individual smaller steps below

        # graypaper-equation: 16
        # [TODO: input 1: Block.Header]
        self.state_transition_16(block.header)

        # graypaper-equation: 17
        # [TODO: input 1: Block.Header]
        # [TODO: input 2: State.recent_blocks of current state]
        self.state_transition_17(block.header, self.recent_blocks)

        # graypaper-equation: 18
        #NOTE: 3rd argument is output op state_transition_17 (intermediate result)
        # [TODO: input 1: Block.Header]
        # [TODO: input 2: Block.Extrinsic.reports]
        # [TODO: input 3: State.recent_blocks of intermediate state (result of graypaper-equation 17]
        # [TODO: input 4: 'C'-object to be determined Beefy related ]
        self.state_transition_18(block.header, block.extrinsic.reports, self.recent_blocks, {})

        # graypaper-equation: 19
        # [TODO: input 1: Block.Header]
        # [TODO: input 2: Timeslot of current state]
        # [TODO: input 3: Block.Extrinsic.tickets]
        # [TODO: input 4: State.safrole of current state]
        # [TODO: input 5: State.enqueued_validators of current state]
        # [TODO: input 6: State.entropy of transitioned state]
        # [TODO: input 7: State.validators of transitioned state]
        self.state_transition_19(block.header, self.timeslot, block.extrinsic.tickets, self.safrole, self.enqueued_validators, self.entropy, self.validators)

        # graypaper-equation: 20
        # [TODO: input 1: Block.Header]
        # [TODO: input 2: Timeslot of current state]
        # [TODO: input 3: State.entropy of current state]
        self.state_transition_20(block.header, self.timeslot, self.entropy)

        # graypaper-equation: 21
        # [TODO: input 1: Block.Header]
        # [TODO: input 2: Timeslot of current state]
        # [TODO: input 3: State.validators of current state]
        # [TODO: input 4: State.safrole of current state]
        # [TODO: input 5: State.disputes of transitioned state]
        self.state_transition_21(block.header, self.timeslot, self.validators, self.safrole, self.disputes)

        #[TODO: output 1: State of transitioned state]
        pass

        # graypaper-equation: 22
        # [TODO: input 1: Block.Header]
        # [TODO: input 2: Timeslot of current state]
        # [TODO: input 3: State.archived_validators of current state]
        # [TODO: input 4: State.validators of current state]
        self.state_transition_22(block.header, self.timeslot, self.archived_validators, self.validators)

        # graypaper-equation: 23
        # [TODO: input 1: Block.Extrinsic.judgements]
        # [TODO: input 2: State.disputes of current state]
        self.state_transition_23(block.extrinsic.judgements, self.disputes)

        # graypaper-equation: 24
        # [TODO: input 1: Block.Extrinsic.preimages]
        # [TODO: input 2: State.services of current state]
        # [TODO: input 3: Timeslot of transitioned state]
        self.state_transition_24(block.extrinsic.preimages, self.services, self.timeslot)

        # graypaper-equation: 25
        # [TODO: input 1: Block.Extrinsic.judgements]
        # [TODO: input 2: State.assurances of current state]
        self.state_transition_25(block.extrinsic.judgements, self.assurances)

        # graypaper-equation: 26
        # [TODO: input 1: Block.Extrinsic.assurances]
        # [TODO: input 2: State.assurances of first intermediate state of graypaper-equation: 25]
        self.state_transition_26(block.extrinsic.assurances, self.assurances)

        # graypaper-equation: 27
        # [TODO: input 1: Block.Extrinsic.reports]
        # [TODO: input 2: State.assurances of second intermediate state of graypaper-equation: 26]
        # [TODO: input 3: State.validators of current state]
        # [TODO: input 4: Timeslot of transitioned state]
        self.state_transition_27(block.extrinsic.reports, self.assurances, self.validators, self.timeslot)

        # graypaper-equation: 28
        # [TODO: input 1: Block.Extrinsic.assurances]
        # [TODO: input 2: State.assurances of transitioned state of graypaper-equation: 27]
        # [TODO: input 3: State.services of intermediate state of graypaper-equation: 24]
        # [TODO: input 4: State.priviliged_services current state]
        # [TODO: input 5: State.enqueued_validators of current state]
        # [TODO: input 6: State.authorizers_queue of current state]
        self.state_transition_28(block.extrinsic.assurances, self.assurances, self.services, self.priviliged_services, self.enqueued_validators, self.authorizers_queue)

        # graypaper-equation: 29
        # [TODO: input 1: Block.Extrinsic.reports]
        # [TODO: input 2: State.authorizers_queue of transitioned state]
        # [TODO: input 3: State.authorizers of current state]
        self.state_transition_29(block.extrinsic.reports, self.authorizers_queue, self.authorizers)

        #[TODO: output 1: State of transitioned state; state is now updated!!]
        pass

    #graypaper-equation: 16
    #[NOTE: no state required as input in graypaper-equation: 16; no 'self' as function input?!?]
    #[TODO: input 1: Block.Header]
    def state_transition_16(header: Header):
        #self.timeslot += 1
        #[TODO: output 1: State.timeslot of transitioned state]
        pass

    #graypaper-equation: 17
    #[NOTES: this function is an intermediate step and creates output that is used in graypaper-equation: 18]
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: State.recent_blocks of current state]
    def state_transition_17(header: Header, i2: {}):
        #[TODO: output 1: State.recent_blocks of intermediate state]
        pass

    #graypaper-equation: 18
    #[NOTE: how can we more explicitly follow GP by only having 'beta' instead of self as input (subset of state)]
    #[NOTE: how can we more explicitly follow GP by only having 'Extrinsic.reports' as input (subset of extrinsic)]
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: Block.Extrinsic.reports]
    #[TODO: input 3: State.recent_blocks of intermediate state (result of graypaper-equation 17]
    #[TODO: input 4: 'C'-object to be determined Beefy related ]
    def state_transition_18(header: Header, i2: {}, i3: {}, i4: {}):
        #[TODO: output 1: State.recent_blocks of transitioned state]
        pass

    #graypaper-equation: 19
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: Timeslot of current state]
    #[TODO: input 3: Block.Extrinsic.tickets]
    #[TODO: input 4: State.safrole of current state]
    #[TODO: input 5: State.enqueued_validators of current state]
    #[TODO: input 6: State.entropy of transitioned state]
    #[TODO: input 7: State.validators of transitioned state]
    def state_transition_19(header: Header, i2: {}, i3: {}, i4: {}, i5: {}, i6: {}, i7: {}):
        #[TODO: output 1: State.safrole of transitioned state]
        pass

    #graypaper-equation: 20
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: Timeslot of current state]
    #[TODO: input 3: State.entropy of current state]
    def state_transition_20(header: Header, i2: {}, i3: {}):
        #[TODO: output 1: State.entropy of transitioned state]
        pass

    #graypaper-equation: 21
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: Timeslot of current state]
    #[TODO: input 3: State.validators of current state]
    #[TODO: input 4: State.safrole of current state]
    #[TODO: input 5: State.disputes of transitioned state]
    def state_transition_21(header: Header, i2: {}, i3: {}, i4: {}, i5: {}):
        #[TODO: output 1: State.validators of transitioned state]
        pass

    #graypaper-equation: 22
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: Timeslot of current state]
    #[TODO: input 3: State.archived_validators of current state]
    #[TODO: input 4: State.validators of current state]
    def state_transition_22(header: Header, i2: {}, i3: {}, i4: {}):
        #[TODO: output 1: State.archived_validators of transitioned state]
        pass

    #graypaper-equation: 23
    #[TODO: input 1: Block.Extrinsic.judgements]
    #[TODO: input 2: State.disputes of current state]
    def state_transition_23(i1: {}, i2: {}):
        #[TODO: output 1: State.disputes of transitioned state]
        pass

    #graypaper-equation: 24
    #[TODO: input 1: Block.Extrinsic.preimages]
    #[TODO: input 2: State.services of current state]
    #[TODO: input 3: Timeslot of transitioned state]
    def state_transition_24(i1: {}, i2: {}, i3: {}):
        #[TODO: output 1: State.services of intermediate state]
        pass

    #graypaper-equation: 25
    #[NOTES: this function is a first intermediate step and creates output that is used in graypaper-equation: 26]
    #[TODO: input 1: Block.Extrinsic.judgements]
    #[TODO: input 2: State.assurances of current state]
    def state_transition_25(i1: {}, i2: {}):
        #[TODO: output 1: State.assurances of first intermediate state]
        pass

    #graypaper-equation: 26
    #[NOTES: this function is a second intermediate step and creates output that is used in graypaper-equation: 27]
    #[TODO: input 1: Block.Extrinsic.assurances]
    #[TODO: input 2: State.assurances of first intermediate state of graypaper-equation: 25]
    def state_transition_26(i1: {}, i2: {}):
        #[TODO: output 1: State.assurances of second intermediate state]
        pass

    #graypaper-equation: 27
    #[TODO: input 1: Block.Extrinsic.reports]
    #[TODO: input 2: State.assurances of second intermediate state of graypaper-equation: 26]
    #[TODO: input 3: State.validators of current state]
    #[TODO: input 4: Timeslot of transitioned state]
    def state_transition_27(i1: {}, i2: {}, i3: {}, i4: {}):
        #[TODO: output 1: State.assurances of transitioned state]
        pass

    #graypaper-equation: 28
    #[TODO: input 1: Block.Extrinsic.assurances]
    #[TODO: input 2: State.assurances of transitioned state of graypaper-equation: 27]
    #[TODO: input 3: State.services of intermediate state of graypaper-equation: 24]
    #[TODO: input 4: State.priviliged_services current state]
    #[TODO: input 5: State.enqueued_validators of current state]
    #[TODO: input 6: State.authorizers_queue of current state]
    def state_transition_28(i1: {}, i2: {}, i3: {}, i4: {}, i5: {}, i6: {}):
        #[TODO: output 1: State.services of transitioned state]
        #[TODO: output 2: State.priviliged_services transitioned state]
        #[TODO: output 3: State.enqueued_validators of transitioned state]
        #[TODO: output 4: State.authorizers_queue of transitioned state]
        #[TODO: output 5: {[}C-object} todo later requires more research]
        pass

    #graypaper-equation: 29
    #[TODO: input 1: Block.Extrinsic.reports]
    #[TODO: input 2: State.authorizers_queue of transitioned state]
    #[TODO: input 3: State.authorizers of current state]
    def state_transition_29(i1: {}, i2: {}, i3: {}):
        #[TODO: output 1: State.authorizers of transitioned state]
        pass


class StateAuthorizers:
    #graypaper-reference: ALPHA
    def __init__(self, state: State):
        #definition
        self.authorizers = {}


class StateRecentBlocks:
    #graypaper-reference: BETA
    def __init__(self, state: State):
        #definition
        self.recent_blocks = [{},{},{},{}]


class StateSafrole:
    #graypaper-reference: GAMMA
    def __init__(self, state: State):
        #definition
        self.safrole = {}


class StateServices:
    #graypaper-reference: DELTA
    def __init__(self, state: State):
        #definition
        self.services = {}


class StateEntropy:
    #graypaper-reference: ETA
    def __init__(self, state: State):
        #definition
        self.entropy = {}


class StateEnqueuedValidators:
    #graypaper-reference: IOTA
    def __init__(self, state: State):
        #definition
        self.enqueued_validators = {}


class StateValidators:
    #graypaper-reference: KAPPA
    def __init__(self, state: State):
        #definition
        self.validators = {}


class StateArchivedValidators:
    #graypaper-reference: LAMBDA
    def __init__(self, state: State):
        #definition
        self.archived_validators = {}


class StateAssurances:
    #graypaper-reference: RHO
    def __init__(self, state: State):
        #definition
        self.assurances = {}


class StateTimeslot:
    #graypaper-reference: TAU
    def __init__(self, state: State):
        #definition
        self.timeslot = 1


class StateAuthorizersQueue:
    #graypaper-reference: PHI
    def __init__(self, state: State):
        #definition
        self.authorizers_queue = {}


class StatePriviligedServices:
    #graypaper-reference: CHI
    def __init__(self, state: State):
        #definition
        self.priviliged_services = {}


class StateDisputes:
    #graypaper-reference: PSI
    def __init__(self, state: State):
        #definition
        self.disputes = {}
