from copy import deepcopy
from dataclasses import dataclass
from typing import List

from pyjamaz.types.safrole import Output
from pyjamaz.state.base import StateManager
from pyjamaz.state.exceptions import StateTransitionError

from pyjamaz.state.managers import Timeslot, Entropy, Safrole, ValidatorArchive, ValidatorPool
from pyjamaz.types.block import Block
from pyjamaz.types.state import JamState


@dataclass
class AppConfig:
    ring_data: bytes


class PyjamazApp:
    def __init__(self, initial_state: JamState, config: AppConfig):
        self.prev_state = initial_state
        self.state = initial_state
        self.config = config

        # Order defined by overall state transition dependency graph GP-0.3.2-eq16-30
        # Todo: strictly define input parameters for STFs. What data is allowed to be used to determine posterior state
        #  of state component.
        self.state_managers: List[StateManager] = [
            Timeslot(current_state=self.state, pre_state=self.state),
            Entropy(current_state=self.state, pre_state=self.state),
            ValidatorArchive(current_state=self.state, pre_state=self.state),
            ValidatorPool(current_state=self.state, pre_state=self.state),
            Safrole(current_state=self.state, pre_state=self.state, ring_data=self.config.ring_data),
        ]

    def process_block(self, block: Block) -> List[Output]:

        post_state = deepcopy(self.state)

        result = []
        for state_manager in self.state_managers:
            # Set copy of state as transaction buffer
            state_manager.state = post_state
            state_manager.post_state = post_state

            try:
                output: Output = state_manager.state_transition(block)

                if output is not None:
                    result.append(output)
            except StateTransitionError as e:
                return [Output(err=e.custom_error_code)]

        # All state managers succesful, commit state changes
        self.prev_state = self.state
        self.state = post_state

        return result
