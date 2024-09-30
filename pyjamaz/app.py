from dataclasses import dataclass
from typing import Type, TypeVar

from pyjamaz.storage import StorageInterface
from pyjamaz.state.base import StateComponent
from pyjamaz.state.manager import StateManager

from pyjamaz.state.components import Timeslot, Entropy, Safrole, ValidatorArchive, ValidatorPool, ValidatorQueue, \
    RecentHistory, Disputes
from pyjamaz.types.block import Block, OutputMarks
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
        self.state_manager.get(Timeslot).store_state(state.timeslot)
        self.state_manager.get(RecentHistory).store_state(state.recent_history)
        self.state_manager.get(Entropy).store_state(state.entropy)
        self.state_manager.get(Disputes).store_state(state.disputes)
        self.state_manager.get(ValidatorArchive).store_state(state.validator_archive)
        self.state_manager.get(ValidatorPool).store_state(state.validator_pool)
        self.state_manager.get(Safrole).store_state(state.safrole)
        self.state_manager.get(ValidatorQueue).store_state(state.validator_queue)

    def validate_block(self, block: Block):
        pass

    def state_transition(self, block: 'Block') -> 'STFOutput':

        # Initialization State Components
        timeslot = Timeslot(self.storage_engine)
        # TODO TBD add when clear how to determine block hash, work_report_hashes and accumulate_root
        # recent_history = self.state_manager.initialize(RecentHistory)
        entropy = self.state_manager.get(Entropy)
        disputes = self.state_manager.get(Disputes)
        validator_pool = self.state_manager.get(ValidatorPool)
        validator_queue = self.state_manager.get(ValidatorQueue)
        validator_archive = self.state_manager.get(ValidatorArchive)
        safrole = self.state_manager.get(Safrole)

        # Retrieve current state
        pre_state_timeslot = timeslot.retrieve_state()
        pre_state_entropy = entropy.retrieve_state()
        pre_state_disputes = disputes.retrieve_state()
        pre_state_safrole = safrole.retrieve_state()
        pre_state_validator_pool = validator_pool.retrieve_state()
        pre_state_validator_archive = validator_archive.retrieve_state()
        pre_state_validator_queue = validator_queue.retrieve_state()

        # Timeslot STF GP-0.3.8-eq:16
        timeslot_output = timeslot.state_transition(header=block.header)

        # Entropy STF GP-0.3.8-eq:20
        entropy_output = entropy.state_transition(
            header=block.header, pre_state_timeslot=pre_state_timeslot, pre_state_entropy=pre_state_entropy
        )

        # Disputes STF GP-0.3.8-eq:23
        disputes_output = disputes.state_transition(
            extrinsic_disputes=block.extrinsic.disputes, pre_state_disputes=pre_state_disputes
        )

        # Validator Pool STF GP-0.3.8-eq:21
        validator_pool_output = validator_pool.state_transition(
            header=block.header,
            pre_state_timeslot=pre_state_timeslot,
            pre_state_validator_pool=pre_state_validator_pool,
            pre_state_safrole=pre_state_safrole,
            post_state_disputes=disputes_output.post_state
        )

        # Validator Archive STF GP-0.3.8-eq:22
        validator_archive_output = validator_archive.state_transition(
            header=block.header, pre_state_timeslot=pre_state_timeslot,
            pre_state_validator_archive=pre_state_validator_archive,
            pre_state_validator_pool=pre_state_validator_pool
        )

        # Safrole STF GP-0.3.8-eq:19
        safrole_output = safrole.state_transition(
            header=block.header, pre_state_timeslot=pre_state_timeslot, extrinsic_tickets=block.extrinsic.tickets,
            pre_state_safrole=pre_state_safrole,
            pre_state_validator_queue=pre_state_validator_queue, post_state_entropy=entropy_output.post_state,
            post_state_validator_pool=validator_pool_output.post_state
        )

        # All state transitions successful, commit state changes
        with self.storage_engine.transaction() as transaction:
            timeslot.store_state(timeslot_output.post_state)
            # TODO TBD add when clear how to determine block hash, work_report_hashes and accumulate_root
            # recent_history = self.state_manager.initialize(RecentHistory)
            entropy.store_state(entropy_output.post_state)
            disputes.store_state(disputes_output.post_state)
            validator_pool.store_state(validator_pool_output.post_state)
            validator_archive.store_state(validator_archive_output.post_state)
            safrole.store_state(safrole_output.post_state)

        return STFOutput(
            output_marks=OutputMarks(
                epoch_mark=safrole_output.output_marks.epoch_mark,
                tickets_mark=safrole_output.output_marks.tickets_mark
            )
        )

    def process_block(self, block: Block) -> STFOutput:

        self.validate_block(block)

        output = self.state_transition(block)

        return output
