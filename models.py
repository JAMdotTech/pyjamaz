from constants import VALIDATOR_COUNT


class Header:
    #graypaper-equation: 36
    def __init__(self):
        self.parent_hash = '0x0000000000000000000000000000000000000000000000000000000000000000'
        self.state_root_prior = '0x0000000000000000000000000000000000000000000000000000000000000000'
        self.extrinsic_hash = '0x0000000000000000000000000000000000000000000000000000000000000000'
        self.timeslot = 1
        self.epoch = '0x00'
        self.winning_tickets_marker = '0x00'
        self.judgements_marker = '0x00'
        self.author_key_idx = 1
        self.vrf_signature = '0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        self.block_seal = '0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'


class Extrinsic:
    #graypaper-equation: 14
    def __init__(self):
        self.tickets = {}
        self.judgements = {}
        self.preimages = {}
        self.availability = {}
        self.reports = {}

class Block:
    #graypaper-equation: 13
    def __init__(self, header: Header, extrinsic: Extrinsic):
        self.header = header
        self.extrinsic = extrinsic

class State:
    #graypaper-equation: 15
    def __init__(self):
        #graypaper-reference: ALPHA
        self.authorizers = {}

        #graypaper-reference: BETA
        self.recent_blocks = [{},{},{},{}]

        #graypaper-reference: GAMMA
        self.safrole = {}

        #graypaper-reference: DELTA
        self.services = {}

        #graypaper-reference: ETA
        self.entropy = {}

        #graypaper-reference: IOTA
        self.enqueued_validators = {}

        #graypaper-reference: KAPPA
        self.validators = {}

        #graypaper-reference: LAMBDA
        self.archived_validators = {}

        #graypaper-reference: RHO
        self.assurances = {}

        #graypaper-reference: TAU
        self.timeslot = 1

        #graypaper-reference: PHI
        self.authorizers_queue = {}

        #graypaper-reference: CHI
        self.priviliged_services = {}

        #graypaper-reference: PSI
        self.disputes = {}

    #graypaper-equation: 12
    #[TODO: input 1: State]
    #[TODO: input 2: Block]
    def state_transition(self, block: Block):
        #[TODO: output 1: State of transitioned state]
        pass

    #graypaper-equation: 16
    #[NOTE: no state required as input in graypaper-equation: 16; no 'self' as function input?!?]
    #[TODO: input 1: Block.Header]
    def state_transition_timeslot(header: Header):
        #self.timeslot += 1
        #[TODO: output 1: State.timeslot of transitioned state]
        pass

    #graypaper-equation: 17
    #[NOTES: this function is an intermediate step and creates output that is used in graypaper-equation: 18]
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: State.recent_blocks of current state]
    def state_transition_recent_17(header: Header, i2: {}):
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
    #[TODO: input 4: State.archived_validators of current state]
    #[TODO: input 3: State.validators of current state]
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
