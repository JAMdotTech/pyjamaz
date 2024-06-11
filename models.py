from constants import VALIDATOR_COUNT


class Header:
    pass


class Extrinsic:
    pass


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

