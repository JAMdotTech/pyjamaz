from dataclasses import dataclass
from typing import Type, TypeVar

from pyjamaz.storage import StorageInterface
from pyjamaz.state.base import StateComponent
from pyjamaz.state.manager import StateManager

from pyjamaz.state.components import Timeslot, Entropy, Safrole, ValidatorArchive, ValidatorPool, ValidatorQueue, \
    RecentHistory, Disputes, Assurances, Statistics, Services, PrivilegedServices, AuthorizerQueues, AuthorizerPools
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
        self.state_manager.add(Assurances)
        self.state_manager.add(ValidatorArchive)
        self.state_manager.add(ValidatorPool)
        self.state_manager.add(Safrole, ring_data=self.config.ring_data)
        self.state_manager.add(ValidatorQueue)
        self.state_manager.add(Statistics)
        # self.state_manager.add(Services)
        self.state_manager.add(AuthorizerQueues)
        self.state_manager.add(PrivilegedServices)
        self.state_manager.add(AuthorizerPools)

    def get_state(self, state_manager: Type[StateComponent]):
        return self.state_manager.get(state_manager).retrieve_state()

    def init_state(self, state: JamState):
        self.state_manager.get(Timeslot).store_state(state.timeslot)
        self.state_manager.get(RecentHistory).store_state(state.recent_history)
        self.state_manager.get(Entropy).store_state(state.entropy)
        self.state_manager.get(Disputes).store_state(state.disputes)
        self.state_manager.get(Assurances).store_state(state.assurances)
        self.state_manager.get(ValidatorArchive).store_state(state.validator_archive)
        self.state_manager.get(ValidatorQueue).store_state(state.validator_queue)
        self.state_manager.get(ValidatorPool).store_state(state.validator_pool)
        self.state_manager.get(Safrole).store_state(state.safrole)
        # self.state_manager.get(Statistics).store_state(state.statistics)
        # self.state_manager.get(Services).store_state(state.services)
        # self.state_manager.get(AuthorizerQueues).store_state(state.authorizer_queues)
        self.state_manager.get(PrivilegedServices).store_state(state.privileged_services)
        self.state_manager.get(AuthorizerPools).store_state(state.authorizer_pools)

    def validate_block(
            self,
            block: Block
    ):
        pass

    def state_transition(
            self,
            block: 'Block'
    ) -> 'STFOutput':
        """
        GP-0.3.8-eq:12 (Υ, σ') | Block Level State Transition Function for the JAM state.

        Implicit parameter 1 | Current State | GP-0.3.8-eq:12 (σ)

        Parameters
        ----------
        block: Block
            Input parameter 2 | Block Data | GP-0.3.8-eq:12 (bold_B)
        """

        # Initialization State Components
        timeslot = Timeslot(self.storage_engine)
        # TODO TBD add when clear how to determine block hash, work_report_hashes and accumulate_root
        # recent_history = self.state_manager.initialize(RecentHistory)
        recent_history = self.state_manager.get(RecentHistory)
        entropy = self.state_manager.get(Entropy)
        disputes = self.state_manager.get(Disputes)
        assurances = self.state_manager.get(Assurances)
        validator_pool = self.state_manager.get(ValidatorPool)
        validator_queue = self.state_manager.get(ValidatorQueue)
        validator_archive = self.state_manager.get(ValidatorArchive)
        safrole = self.state_manager.get(Safrole)
        # statistics = self.state_manager.get(Statistics)
        # services = self.state_manager.get(Services)
        # authorizer_queues = self.state_manager.get(AuthorizerQueues)
        privileged_services = self.state_manager.get(PrivilegedServices)
        authorizer_pools = self.state_manager.get(AuthorizerPools)

        # Retrieve current state
        pre_state_timeslot = timeslot.retrieve_state()
        pre_state_recent_history = recent_history.retrieve_state()
        pre_state_entropy = entropy.retrieve_state()
        pre_state_disputes = disputes.retrieve_state()
        pre_state_assurances = assurances.retrieve_state()
        pre_state_safrole = safrole.retrieve_state()
        pre_state_validator_pool = validator_pool.retrieve_state()
        pre_state_validator_archive = validator_archive.retrieve_state()
        pre_state_validator_queue = validator_queue.retrieve_state()
        # Todo: implement state component key (well known)
        # pre_state_statistics = statistics.retrieve_state()
        # pre_state_services = services.retrieve_state()
        # pre_state_authorizer_queues = authorizer_queues.retrieve_state()
        pre_state_privileged_services = privileged_services.retrieve_state()
        pre_state_authorizer_pools = authorizer_pools.retrieve_state()

        # Timeslot STF GP-0.3.8-eq:16
        timeslot_output = timeslot.state_transition(
            header=block.header
        )

        # RecentHistoryIntermediate STF GP-0.3.8-eq:17
        recent_history_intermediate_output = recent_history.state_transition_intermediate(
            header=block.header,
            pre_state_recent_history=pre_state_recent_history
        )

        # Entropy STF GP-0.3.8-eq:20
        entropy_output = entropy.state_transition(
            header=block.header,
            pre_state_timeslot=pre_state_timeslot,
            pre_state_entropy=pre_state_entropy
        )

        # Disputes STF GP-0.3.8-eq:23
        disputes_output = disputes.state_transition(
            extrinsic_disputes=block.extrinsic.disputes,
            pre_state_disputes=pre_state_disputes
        )

        # Assurances After Disputes STF GP-0.3.8-eq:25
        assurances_after_disputes_output = assurances.state_transition_after_disputes(
            extrinsic_disputes=block.extrinsic.disputes,
            pre_state_assurances=pre_state_assurances
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
            header=block.header,
            pre_state_timeslot=pre_state_timeslot,
            pre_state_validator_archive=pre_state_validator_archive,
            pre_state_validator_pool=pre_state_validator_pool
        )

        # Safrole STF GP-0.3.8-eq:19
        safrole_output = safrole.state_transition(
            header=block.header,
            pre_state_timeslot=pre_state_timeslot,
            extrinsic_tickets=block.extrinsic.tickets,
            pre_state_safrole=pre_state_safrole,
            pre_state_validator_queue=pre_state_validator_queue,
            post_state_entropy=entropy_output.post_state,
            post_state_validator_pool=validator_pool_output.post_state
        )

        # Statistics STF GP-0.3.8-eq:30
        #statistics_output = statistics.state_transition(
        #    extrinsic_guarantees=block.extrinsic.guarantees,
        #    extrinsic_preimages=block.extrinsic.preimages,
        #    extrinsic_assurances=block.extrinsic.assurances,
        #    extrinsic_tickets=block.extrinsic.tickets,
        #    pre_state_timeslot=pre_state_timeslot,
        #    post_state_timeslot=timeslot_output.post_state,
        #    post_state_validator_pool=validator_pool_output.post_state,
        #    pre_state_statistics=pre_state_statistics,
        #    header=block.header
        #)

        # Assurances After Assurances STF GP-0.3.8-eq:26
        assurances_after_assurances_output = assurances.state_transition_after_assurances(
            extrinsic_assurances=block.extrinsic.assurances,
            intermediate_state_assurances_after_disputes=assurances_after_disputes_output.intermediate_state_after_disputes
        )

        # Services After Preimages STF GP-0.3.8-eq:24
        #services_after_preimages_output = services.state_transition_after_preimages(
        #    extrinsic_preimages=block.extrinsic.preimages,
        #    pre_state_services=pre_state_services,
        #    post_state_timeslot=timeslot_output.post_state
        #)

        # Assurances After Guarantees STF GP-0.3.8-eq:27
        assurances_output = assurances.state_transition_after_guarantees(
            extrinsic_guarantees=block.extrinsic.guarantees,
            intermediate_state_assurances_after_assurances=assurances_after_assurances_output.intermediate_state_after_assurances,
            pre_state_validator_pool=pre_state_validator_pool,
            post_state_timeslot=timeslot_output.post_state
        )

        # Services Accumulation STF GP-0.3.8-eq:28
        #services_output = services.state_transition(
        #    extrinsic_assurances=block.extrinsic.assurances,
        #    post_state_assurances=assurances_output.post_state,
        #    intermediate_state_services_after_preimages=services_after_preimages_output.intermediate_state_after_preimages,
        #    pre_state_privileged_services=pre_state_privileged_services,
        #    pre_state_validator_queue=pre_state_validator_queue,
        #    pre_state_authorizer_queues=pre_state_authorizer_queues
        #)

        # AuthorizerPools STF GP-0.3.8-eq:29
        #authorizer_pools_output = authorizer_pools.state_transition(
        #    header=block.header,
        #    extrinsic_guarantees=block.extrinsic.guarantees,
        #    # Todo: posterior state of authorizer_queues determined by service accumulation (privileged_services)
        #    post_state_authorizer_queues=authorizer_queues_output.post_state,
        #    pre_state_authorizer_pools=pre_state_authorizer_pools
        #)

        # RecentHistory STF GP-0.3.8-eq:18
        #recent_history_output = recent_history.state_transition(
        #    header=block.header,
        #    extrinsic_guarantees=block.extrinsic.guarantees,
        #    intermediate_state_recent_history=recent_history_intermediate_output.intermediate_state,
        #    # Todo: BeefyCommitmentMap is determined by service accumulation (part of STF secondary output)
        #    accumulate_root=services_output.beefy_commitment_map
        #)

        # All state transitions successful, commit state changes
        with self.storage_engine.transaction() as transaction:
            timeslot.store_state(timeslot_output.post_state)
            entropy.store_state(entropy_output.post_state)
            disputes.store_state(disputes_output.post_state)
            validator_pool.store_state(validator_pool_output.post_state)
            validator_archive.store_state(validator_archive_output.post_state)
            safrole.store_state(safrole_output.post_state)
            assurances.store_state(assurances_output.post_state)
            # Todo: add remaining state components: recent_history, services, authorizer_pools, statistics
            # Todo: research but likely also add posterior state of privileged services output (validator_queue, authorization_queues, privileged_services)
            # TODO TBD add when clear how to determine block hash, work_report_hashes and accumulate_root (deprecated by previous todo)
            # recent_history = self.state_manager.initialize(RecentHistory)

        return STFOutput(
            output_marks=OutputMarks(
                epoch_mark=safrole_output.output_marks.epoch_mark,
                tickets_mark=safrole_output.output_marks.tickets_mark
                # Todo: add offenders_mark
                # offenders_mark = disputes_output.output_marks.offenders_mark
            )
        )

    def process_block(self, block: Block) -> STFOutput:

        self.validate_block(block)

        output = self.state_transition(block)

        return output
