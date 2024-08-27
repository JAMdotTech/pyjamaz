from copy import deepcopy
from dataclasses import dataclass
from typing import List, Type, TypeVar

from pyjamaz.storage import JSONStorage, StorageInterface
from pyjamaz.types.safrole import Output
from pyjamaz.state.base import StateManager, StateComponent
from pyjamaz.state.exceptions import StateTransitionError

from pyjamaz.state.components import Timeslot, Entropy, Safrole, ValidatorArchive, ValidatorPool, ValidatorQueue
from pyjamaz.types.block import Block
from pyjamaz.types.state import JamState, TimeslotState, ValidatorQueueState, EntropyState, SafroleState, \
    ValidatorPoolState, ValidatorArchiveState
from scalecodec.base import ScaleBytes

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

        # self.storage_state = self.retrieve_state_from_storage()

    def get_state(self, state_manager: Type[StateComponent]):
        return self.state_components.get(state_manager.component_id).retrieve_state()

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

    def process_block(self, block: Block) -> List[Output]:

        result = []

        # with self.storage_engine.transaction as tx_buffer:

        for state_component in self.state_components:
            # Set copy of state as transaction buffer
            state_component.pre_state = state_component.retrieve_state()
            state_component.post_state = state_component.retrieve_state()

            try:
                # TODO use transaction and set so store function will use this
                output: Output = state_component.state_transition(block)

                if output is not None:
                    result.append(output)
            except StateTransitionError as e:
                return [Output(err=e.custom_error_code)]

        # All state managers succesful, commit state changes
        for state_component in self.state_components:
            state_component.store_state()

        return result
