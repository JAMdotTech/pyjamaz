from copy import deepcopy
from dataclasses import dataclass
from typing import List, Type, TypeVar

from pyjamaz.storage import JSONStorage, StorageInterface
from pyjamaz.types.safrole import Output
from pyjamaz.state.base import StateManager
from pyjamaz.state.exceptions import StateTransitionError

from pyjamaz.state.managers import Timeslot, Entropy, Safrole, ValidatorArchive, ValidatorPool, ValidatorQueue
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
        # Todo: strictly define input parameters for STFs. What data is allowed to be used to determine posterior state
        #  of state component.

        # self.state_managers: List[StateManager] = [
        #     Timeslot(storage_engine=self.storage_engine),
        #     Entropy(storage_engine=self.storage_engine),
        #     ValidatorArchive(storage_engine=self.storage_engine),
        #     ValidatorPool(storage_engine=self.storage_engine),
        #     Safrole(storage_engine=self.storage_engine,  ring_data=self.config.ring_data),
        #     ValidatorQueue(storage_engine=self.storage_engine)
        # ]

        self.state_managers = {}

        self.add_state_manager(Timeslot)
        self.add_state_manager(Entropy)
        self.add_state_manager(ValidatorArchive)
        self.add_state_manager(ValidatorPool)
        self.add_state_manager(Safrole, ring_data=self.config.ring_data)
        self.add_state_manager(ValidatorQueue)

        # self.storage_state = self.retrieve_state_from_storage()

    def add_state_manager(self, state_manager: Type[StateManager], **args):
        self.state_managers[state_manager] = state_manager(
            self.storage_engine, self, **args
        )

    def get_state(self, state_manager: Type[StateManager]):
        return self.state_managers[state_manager].retrieve_state()

    def init_state(self, state: JamState):
        self.state_managers[Timeslot].pre_state = state.timeslot
        self.state_managers[Timeslot].post_state = state.timeslot
        self.state_managers[Timeslot].store_state()

        self.state_managers[Entropy].pre_state = state.entropy
        self.state_managers[Entropy].post_state = state.entropy
        self.state_managers[Entropy].store_state()

        self.state_managers[ValidatorArchive].pre_state = state.validator_archive
        self.state_managers[ValidatorArchive].post_state = state.validator_archive
        self.state_managers[ValidatorArchive].store_state()

        self.state_managers[ValidatorPool].pre_state = state.validator_pool
        self.state_managers[ValidatorPool].post_state = state.validator_pool
        self.state_managers[ValidatorPool].store_state()

        self.state_managers[Safrole].pre_state = state.safrole
        self.state_managers[Safrole].post_state = state.safrole
        self.state_managers[Safrole].store_state()

        self.state_managers[ValidatorQueue].pre_state = state.validator_queue
        self.state_managers[ValidatorQueue].post_state = state.validator_queue
        self.state_managers[ValidatorQueue].store_state()

    def process_block(self, block: Block) -> List[Output]:

        result = []

        # with self.storage_engine.transaction as tx_buffer:

        for state_manager in self.state_managers.values():
            # Set copy of state as transaction buffer
            state_manager.pre_state = state_manager.retrieve_state()
            state_manager.post_state = state_manager.retrieve_state()

            try:
                # TODO use transaction and set so store function will use this
                output: Output = state_manager.state_transition(block)

                if output is not None:
                    result.append(output)
            except StateTransitionError as e:
                return [Output(err=e.custom_error_code)]

        # All state managers succesful, commit state changes
        for state_manager in self.state_managers.values():
            state_manager.store_state()

        return result
