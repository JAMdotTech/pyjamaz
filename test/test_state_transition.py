import unittest

from models import Validator, Header, Extrinsic, Block
from models.state.state import State


class TestStateTransition(unittest.TestCase):

    def test_valid_timeslot(self):
        validator_alice = Validator()
        validator_bob = Validator()
        validator_charlie = Validator()

        state = State(
            validators=[validator_alice, validator_bob, validator_charlie],
            timeslot=0
        )

        header = Header()
        extrinsic = Extrinsic()
        block = Block(header, extrinsic)

        state.state_transition(block=block)

        self.assertEquals(1, state.timeslot)

    def test_invalid_validator_count(self):
        validator_alice = Validator()
        validator_bob = Validator()
        validator_charlie = Validator()

        with self.assertRaises(ValueError) as exc:
            state = State(
                validators=[validator_alice, validator_bob, validator_charlie],
                timeslot=0
            )


