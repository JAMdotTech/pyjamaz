from dataclasses import dataclass
from typing import Type, TypeVar

from pyjamaz.storage import StorageInterface
from pyjamaz.state.base import StateComponent
from pyjamaz.state.manager import StateManager

from pyjamaz.state.components import Timeslot, Entropy, Safrole, ValidatorArchive, ValidatorPool, ValidatorQueue, \
    RecentHistory, Disputes
from pyjamaz.types.block import Block
from pyjamaz.types.state import JamState
from pyjamaz.types.stf_output import STFOutput

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
        self.state_manager = StateManager(self.storage_engine)

        self.state_manager.add(Timeslot)
        self.state_manager.add(RecentHistory)
        self.state_manager.add(Entropy)
        self.state_manager.add(Disputes)
        self.state_manager.add(ValidatorArchive)
        self.state_manager.add(ValidatorPool)
        self.state_manager.add(Safrole, ring_data=self.config.ring_data)
        self.state_manager.add(ValidatorQueue)

    def get_state(self, state_manager: Type[StateComponent]):
        return self.state_manager.get(state_manager).retrieve_state()

    def init_state(self, state: JamState):
        self.state_manager.get(Timeslot).pre_state = state.timeslot
        self.state_manager.get(Timeslot).post_state = state.timeslot
        self.state_manager.get(Timeslot).store_state()

        self.state_manager.get(RecentHistory).pre_state = state.recent_history
        self.state_manager.get(RecentHistory).post_state = state.recent_history
        self.state_manager.get(RecentHistory).store_state()

        self.state_manager.get(Entropy).pre_state = state.entropy
        self.state_manager.get(Entropy).post_state = state.entropy
        self.state_manager.get(Entropy).store_state()

        self.state_manager.get(Disputes).pre_state = state.disputes
        self.state_manager.get(Disputes).post_state = state.disputes
        self.state_manager.get(Disputes).store_state()

        self.state_manager.get(ValidatorArchive).pre_state = state.validator_archive
        self.state_manager.get(ValidatorArchive).post_state = state.validator_archive
        self.state_manager.get(ValidatorArchive).store_state()

        self.state_manager.get(ValidatorPool).pre_state = state.validator_pool
        self.state_manager.get(ValidatorPool).post_state = state.validator_pool
        self.state_manager.get(ValidatorPool).store_state()

        self.state_manager.get(Safrole).pre_state = state.safrole
        self.state_manager.get(Safrole).post_state = state.safrole
        self.state_manager.get(Safrole).store_state()

        self.state_manager.get(ValidatorQueue).pre_state = state.validator_queue
        self.state_manager.get(ValidatorQueue).post_state = state.validator_queue
        self.state_manager.get(ValidatorQueue).store_state()

    def validate_block(self, block: Block):
        pass

    def state_transition(self, block: 'Block') -> 'STFOutput':

        # Initialization State Components
        timeslot = self.state_manager.initialize(Timeslot)
        # TODO TBD add when clear how to determine block hash, work_report_hashes and accumulate_root
        # recent_history = self.state_manager.initialize(RecentHistory)
        entropy = self.state_manager.initialize(Entropy)
        disputes = self.state_manager.initialize(Disputes)
        validator_pool = self.state_manager.initialize(ValidatorPool)
        validator_queue = self.state_manager.initialize(ValidatorQueue)
        validator_archive = self.state_manager.initialize(ValidatorArchive)
        safrole = self.state_manager.initialize(Safrole)

        # Timeslot STF GP-0.3.7-eq:16
        timeslot.state_transition(header=block.header)

        # Entropy STF GP-0.3.7-eq:20
        entropy.state_transition(header=block.header, pre_state_timeslot=timeslot.pre_state)

        # Disputes STF GP-0.3.7-eq:23
        disputes.state_transition(block.extrinsic.disputes)

        # Validator Pool STF GP-0.3.7-eq:21
        validator_pool.state_transition(
            header=block.header, pre_state_timeslot=timeslot.pre_state,
            pre_state_safrole=safrole.pre_state, post_state_disputes=disputes.post_state
        )

        # Validator Archive STF GP-0.3.7-eq:22
        validator_archive.state_transition(
            header=block.header, pre_state_timeslot=timeslot.pre_state,
            pre_state_validator_pool=validator_pool.pre_state
        )

        # Safrole STF GP-0.3.7-eq:19
        safrole_output = safrole.state_transition(
            header=block.header, pre_state_timeslot=timeslot.pre_state, extrinsic_tickets=block.extrinsic.tickets,
            pre_state_validator_queue=validator_queue.pre_state, post_state_entropy=entropy.post_state,
            post_state_validator_pool=validator_pool.post_state
        )

        # All state transitions succesful, commit state changes
        with self.storage_engine.transaction() as transaction:
            for state_component in self.state_manager.state_components.values():
                state_component.store_state(transaction)

        return STFOutput(safrole=safrole_output)

    def process_block(self, block: Block) -> STFOutput:

        self.validate_block(block)

        output = self.state_transition(block)

        return output
