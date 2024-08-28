from dataclasses import dataclass
from typing import List, Type, TypeVar

from pyjamaz.storage import StorageInterface
from pyjamaz.types.safrole import OutputMarks
from pyjamaz.state.base import StateManager, StateComponent

from pyjamaz.state.components import Timeslot, Entropy, Safrole, ValidatorArchive, ValidatorPool, ValidatorQueue
from pyjamaz.types.block import Block
from pyjamaz.types.state import JamState

T = TypeVar('T')


@dataclass
class AppConfig:
    ring_data: bytes
    storage_engine: StorageInterface


class PyjamazApp:
    def __init__(self, config: AppConfig):
        self.config = config

        self.storage_engine = config.storage_engine

        # Order defined by overall state transition dependency graph GP-0.3.2-eq16-30
        self.state_components = StateManager(self.storage_engine)

        self.state_components.add(Timeslot)
        self.state_components.add(Entropy)
        self.state_components.add(ValidatorArchive)
        self.state_components.add(ValidatorPool)
        self.state_components.add(Safrole, ring_data=self.config.ring_data)
        self.state_components.add(ValidatorQueue)

    def get_state(self, state_manager: Type[StateComponent]):
        return self.state_components.get(state_manager).retrieve_state()

    def init_state(self, state: JamState):
        self.state_components.get(Timeslot).pre_state = state.timeslot
        self.state_components.get(Timeslot).post_state = state.timeslot
        self.state_components.get(Timeslot).store_state()

        self.state_components.get(Entropy).pre_state = state.entropy
        self.state_components.get(Entropy).post_state = state.entropy
        self.state_components.get(Entropy).store_state()

        self.state_components.get(ValidatorArchive).pre_state = state.validator_archive
        self.state_components.get(ValidatorArchive).post_state = state.validator_archive
        self.state_components.get(ValidatorArchive).store_state()

        self.state_components.get(ValidatorPool).pre_state = state.validator_pool
        self.state_components.get(ValidatorPool).post_state = state.validator_pool
        self.state_components.get(ValidatorPool).store_state()

        self.state_components.get(Safrole).pre_state = state.safrole
        self.state_components.get(Safrole).post_state = state.safrole
        self.state_components.get(Safrole).store_state()

        self.state_components.get(ValidatorQueue).pre_state = state.validator_queue
        self.state_components.get(ValidatorQueue).post_state = state.validator_queue
        self.state_components.get(ValidatorQueue).store_state()

    def state_transition(self, block: Block) -> OutputMarks:

        output_marks = OutputMarks()

        for state_component in self.state_components:
            # Set copy of state in memory TODO how to manage this for services?

            state_component.initialize(
                pre_state=state_component.retrieve_state(),
                post_state=state_component.retrieve_state(),
                output_marks=output_marks
            )

            state_component.state_transition(block)

        # All state transitions succesful, commit state changes
        with self.storage_engine.transaction() as transaction:
            for state_component in self.state_components:
                state_component.store_state(transaction)

        return output_marks
