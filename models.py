from constants import VALIDATOR_COUNT


class Header:
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
    def __init__(self):
        self.tickets = {}
        self.judgements = {}
        self.preimages = {}
        self.availability = {}
        self.reports = {}

class Block:

    def __init__(self, header: Header, extrinsic: Extrinsic):
        self.header = header
        self.extrinsic = extrinsic


class Validator:
    pass


class State:
    def __init__(self, validators: list, timeslot: int):
        if len(validators) != VALIDATOR_COUNT:
            raise ValueError('incorrect validator count')
        self.validators = validators
        self.timeslot = timeslot

    def state_transition(self, block: Block):
        #self.timeslot += 1
        pass

