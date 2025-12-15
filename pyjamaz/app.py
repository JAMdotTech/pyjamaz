import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from functools import partial
from typing import TypeVar, Optional, List, Callable, Dict, Tuple

from bandersnatch_vrfs import ietf_vrf_sign, RingContext

from jamcodec.base import JamBytes
from jamcodec.mixins import Serializable
from jamcodec.types import Vec, BitArray
from pyjamaz import settings

from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.exceptions import PyjamazAppError, ProcessWorkpackageError, StateTransitionError, \
    BlockValidationErrorCode, BlockValidationError
from pyjamaz.extrinsic import BlockExtrinsicAccumulator, WorkpackageExtrinsicAccumulator
from pyjamaz.graypaper_constants import CORE_COUNT, EPOCH_TIMESLOTS, \
    SLOT_PERIOD, MAXIMUM_AGE_LOOKUP_ANCHOR, MAXIMUM_SIZE_ENCODED_WORK_REPORT, EC_SEGMENT_SIZE
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.hostcalls.invocation import pvm_invoke_is_authorized, pvm_invoke_refine
from pyjamaz.merkle import ConstantDepthMerkleTree
from pyjamaz.models.app import StateDump, Trace
from pyjamaz.models.common import WorkPackage, WorkReport, WorkPackageBundle, WorkPackageQueueItem, WorkPackageStatus, \
    WorkPackageReportableStatus, WorkPackageReadyStatus, BlockDesc, WorkPackageReportedStatus, WorkExecResult, \
    WorkDigest, WorkPackageSpec
from pyjamaz.settings import SOLO_MODE, DEBUG
from pyjamaz.signing import Ed25519Keypair, BandersnatchKeypair
from pyjamaz.models.context import AppContext, BlockContext
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import StorageEngine

from pyjamaz.state.components import Timeslot, Entropy, Safrole, ValidatorArchive, ValidatorPool, ValidatorQueue, \
    RecentHistory, Disputes, Assurances, Statistics, PrivilegedServices, AuthorizerQueues, AuthorizerPools, Services, \
    AccumulationQueue, AccumulationHistory, RecentAccumulationLog
from pyjamaz.models.block import Block, Header, Extrinsic, ExtrinsicDisputes, Guarantee, Credential, \
    Assurance
from pyjamaz.models.state import JamState, ServicesState, SafroleState, EntropyState, PendingChanges
from pyjamaz.models.stf_output import STFOutput
from pyjamaz.transport.pubsub import PubSub, PubSubSignal
from pyjamaz.utils import vrf_input_fallback_seal, vrf_input_ticket_seal, format_hash, log_execution_time, flatten_list
from pyjamaz.validation import BlockValidation

T = TypeVar('T')


@dataclass
class Keys(Serializable):
    bandersnatch: BandersnatchKeypair = field(metadata={'codec': BandersnatchKeypair.to_codec_def()})
    ed25519: 'Ed25519Keypair' = field(metadata={'codec': Ed25519Keypair.to_codec_def()})

    @classmethod
    def from_seed(cls, seed: bytes) -> 'Keys':
        return cls(
            bandersnatch = BandersnatchKeypair.from_seed(blake2b_256_hash(b"jam_val_key_bandersnatch" + seed)),
            ed25519 = Ed25519Keypair.from_seed(blake2b_256_hash(b"jam_val_key_ed25519" + seed))
        )


@dataclass
class AppConfig:
    ring_data: bytes
    storage_engine: StorageEngine
    common_era: int
    keys: Optional[Keys] = field(default=None)
    create_traces: bool = field(default=False)


class PyjamazApp:
    def __init__(self, config: AppConfig, import_block_callback: Callable = None):
        self.config = config

        self.state_db: StorageEngine = config.storage_engine.namespace(b"state")
        self.block_db: StorageEngine = config.storage_engine.namespace(b"block")
        self.app_db: StorageEngine = config.storage_engine.namespace(b"app")
        self.network_bootstrap: bool = False
        self.import_queue: List[Block] = []
        self.pubsub:PubSub = None

        self.state_storage = StateStorage(storage_engine=self.state_db)

        self.block_context = BlockContext()

        self.app_context = AppContext(state_storage=self.state_storage)

        self.import_lock = asyncio.Lock()

        self.components = StateComponents(
            config=self.config,
            block_context=self.block_context,
            app_context=self.app_context
        )

        self.block_extrinsic = BlockExtrinsicAccumulator(self.config.ring_data)

        # Refine
        self.work_package_queue: Dict[bytes, WorkPackageQueueItem] = {}
        self.work_package_extrinsics = WorkpackageExtrinsicAccumulator()
        self.segment_store: Dict[bytes, List[bytes]] = {}

        self.working_state: Optional[JamState] = None

        # Note:
        # For the import block function, we allow the option to provide a custom function (for example to augment with
        # traces or other debug info)
        if import_block_callback:
            self.import_block = partial(import_block_callback, self)
        else:
            self.import_block = self._import_block


    async def import_block_from_bytes(self, data):
        block = Block.from_jam_bytes(JamBytes(data))
        DEBUG and logging.debug(f"📦 Importing block {block.header.timeslot} from bytes")
        self.import_queue.append(block)

        # Note: when we receive a block announcement and we just started our node, we send out a blocks request to sync our state
        if self.network_bootstrap:
            # TODO: app.protocol.conn_out is a temporary hack, should do this different, and also allow for sequential back requests until a certain state is reached
            if self.protocol.conn_out:
                self.network_bootstrap = False
                # TODO: determine peer to request blocks from using protocol grid
                # TODO: moeten we hier niet alleen de header meegeven ipv een heel block te serializen?????
                await self.protocol.request_blocks(0, 100, block.to_jam_bytes().to_bytes())
                # TODO: wel dit block al opslaan en alleen blocks die we vanaf dit Block
        elif block.header.parent == bytes(32) or self.retrieve_block_by_hash(block.header.parent):
            # Note: If we are able to find the parent of this block, it means we are synced and we can process blocks
            await self.process_import_queue()
        else:
            logging.info(f"Syncing in progress, current timeslot={self.working_state.timeslot.number}")


    async def import_block_from_json(self, data):
        DEBUG and logging.debug(f"📦 Importing block from json")
        block = Block.from_json(data)
        await self.import_block(block)


    async def requested_blocks_from_json(self, data):
        block_list = [Block.from_json(block_data) for block_data in data]
        for block in block_list:
            self.import_queue.append(Block.from_codec_type(block))
            logging.info(f"📦 Queue block requested #{block.header.timeslot}")
        await self.process_import_queue()


    async def requested_blocks_from_bytes(self, data):
        block_list = Vec(Block.to_codec_def()).new()
        block_list.decode(JamBytes(data))
        for block_bytes in block_list:
            block = Block.from_codec_type(block_bytes)
            self.import_queue.append(block)

        await self.process_import_queue()


    async def process_import_queue(self):
        async with self.import_lock:
            sorted_blocks = sorted(self.import_queue, key=lambda x: x.header.timeslot)
            self.import_queue = []

        for block in sorted_blocks:
            # TODO: protocol should only import blocks from this point on -> fix the block_request
            if self.working_state.timeslot.number >= block.header.timeslot:
                DEBUG and logging.debug(f" TEMP BREAK block from process_import_queue: {block.header.timeslot}")
                continue

            await self.import_block(block)
            DEBUG and logging.debug(f'✅ Block {block.header.timeslot} successfully imported from process_import_queue.')


    async def initialize(self, header: Optional[Header] = None, produce=False):
        """
        Initialize the app to work with provided header. Sets parent and working state to match parent_state_root
        """
        if header is None:
            # Set to finalized state
            self.state_storage.clear_block_hash()
        else:
            # Update working block hash
            if produce:
                self.state_storage.set_temporary_block_hash(header.parent)
            else:
                self.state_storage.set_block_hash(header.hash, header.parent)

        # Check if parent and state root are matching current working state
        if self.working_state is None or header is None or header.parent_state_root != self.working_state.state_root:
            # update working state
            if header is None:
                DEBUG and logging.debug(
                    f"Updating working state to finalized state @ {format_hash(self.state_storage.finalized_block_hash)}"
                )
            else:
                DEBUG and logging.debug(
                    f"Updating working state to state_root={format_hash(header.parent_state_root)} to match block hash={format_hash(header.parent)}"
                    )
            self.working_state = self.retrieve_jam_state()
            DEBUG and logging.debug(f"Updated working state to state_root={format_hash(self.working_state.state_root)}")

        else:
            DEBUG and logging.debug("StateStorage: State already matches requested state root, no updating required")

    def retrieve_ancestor_headers(self, block_hash: bytes) -> List[Header]:
        """
        GP-0.7.1-eq:5.3 | We only require implementations to store headers of ancestors which were authored in the
        previous (constant_L) = 24 hours of any block (bold_B) they wish to validate.
        """
        ancestor_headers = []
        DEBUG and logging.debug(f"Retrieving ancestor headers from block_hash={format_hash(block_hash)}")

        header = self.retrieve_block_header(block_hash)
        ancestor_headers.append(header)
        for i in range(MAXIMUM_AGE_LOOKUP_ANCHOR):
            header = self.retrieve_block_header(header.parent)
            if header is not None:
                ancestor_headers.append(header)
            else:
                break

        return ancestor_headers

    @log_execution_time
    def retrieve_jam_state(self) -> JamState:
        jam_state = JamState(
            timeslot=self.components.timeslot.retrieve_state(),
            entropy=self.components.entropy.retrieve_state(),
            safrole=self.components.safrole.retrieve_state(),
            validator_queue=self.components.validator_queue.retrieve_state(),
            validator_pool=self.components.validator_pool.retrieve_state(),
            validator_archive=self.components.validator_archive.retrieve_state(),
            authorizer_pools=self.components.authorizer_pools.retrieve_state(),
            recent_history=self.components.recent_history.retrieve_state(),
            services=ServicesState(services={}),
            assurances=self.components.assurances.retrieve_state(),
            authorizer_queues=self.components.authorizer_queues.retrieve_state(),
            privileged_services=self.components.privileged_services.retrieve_state(),
            disputes=self.components.disputes.retrieve_state(),
            statistics=self.components.statistics.retrieve_state(),
            accumulation_queue=self.components.accumulation_queue.retrieve_state(),
            accumulation_history=self.components.accumulation_history.retrieve_state(),
            recent_accumulation_outputs = self.components.recent_accumulation_output.retrieve_state(),
            block_hash=self.state_storage.block_hash,
            state_root=self.state_storage.state_root(),
        )
        # Set storage engine for services
        jam_state.services.set_state_storage(self.state_storage)
        jam_state.services.pending_changes = PendingChanges()
        return jam_state

    @log_execution_time
    async def store_jam_state(self):
        await self.components.timeslot.store_state(self.working_state.timeslot)
        await self.components.entropy.store_state(self.working_state.entropy)
        await self.components.disputes.store_state(self.working_state.disputes)
        await self.components.validator_pool.store_state(self.working_state.validator_pool)
        await self.components.validator_archive.store_state(self.working_state.validator_archive)
        await self.components.safrole.store_state(self.working_state.safrole)
        await self.components.assurances.store_state(self.working_state.assurances)
        await self.components.statistics.store_state(self.working_state.statistics)
        await self.components.services.store_state(self.working_state.services)
        await self.components.recent_history.store_state(self.working_state.recent_history)
        await self.components.authorizer_pools.store_state(self.working_state.authorizer_pools)
        await self.components.authorizer_queues.store_state(self.working_state.authorizer_queues)
        await self.components.accumulation_queue.store_state(self.working_state.accumulation_queue)
        await self.components.accumulation_history.store_state(self.working_state.accumulation_history)
        await self.components.validator_queue.store_state(self.working_state.validator_queue)
        await self.components.privileged_services.store_state(self.working_state.privileged_services)
        await self.components.recent_accumulation_output.store_state(
            self.working_state.recent_accumulation_outputs
            )

    def is_epoch_change(self, slotnumber: int = None) -> bool:
        """
        GP-0.7.1-general: `e!=e' ? T, F` | Helper function that determines if the epoch has changed.

        Returns
        -------
        bool
            `True` when epoch has changed, `False` otherwise.

        TODO duplicate code, move to dedicated package?
        """
        if slotnumber is None:
            slotnumber = self.current_timeslot()

        return self.working_state.timeslot.number // EPOCH_TIMESLOTS != slotnumber // EPOCH_TIMESLOTS

    @log_execution_time
    async def state_transition(self, block: 'Block', produce=False) -> 'STFOutput':
        """
        GP-0.7.1-eq:4.1 (Υ, σ') | Block Level State Transition Function for the JAM state.

        Implicit first parameter (self) | Current State | GP-0.7.1-eq:4.1 (σ)

        Parameters
        ----------
        block: Block
            Block Data | GP-0.7.1-eq:4.1 (bold_B)
        produce: bool

        Returns
        ----------
        STFOutput
        """

        # Validate quality of header data (initial stage)

        # GP-0.7.0-eq:5.7
        if not settings.SKIP_TIMESLOT_WALL_CLOCK_CHECK and block.header.timeslot > self.current_timeslot():
            raise StateTransitionError(BlockValidationErrorCode.bad_slot)

        #  GP-0.7.0-eq:5.4 | Check extrinsic hash
        if block.header.extrinsic_hash != block.extrinsic.generate_extrinsic_hash():
            raise StateTransitionError(BlockValidationErrorCode.extrinsic_hash_mismatch)

        # Retrieve parent header
        parent_header = self.state_storage.get_parent(block.header)

        if parent_header is None:
            DEBUG and logging.debug(f"Parent hash {format_hash(block.header.parent)} does not has a valid ancestor")
            raise StateTransitionError(BlockValidationErrorCode.bad_slot)

        # GP-0.7.0-eq:5.7
        if block.header.timeslot <= parent_header.timeslot:
            raise StateTransitionError(BlockValidationErrorCode.bad_slot)

        # Reset block context
        self.block_context.reset()

        # Start transaction
        self.state_storage.start_tx()

        if not produce:
            # todo refactor
            self.block_context.seal_vrf_output = bytes(96)

        # Set up validation
        block_validation = BlockValidation(self.block_context)

        await self.initialize(header=block.header, produce=produce)

        if block.header.parent_state_root != self.working_state.state_root:
            DEBUG and logging.debug(f"Parent state root {format_hash(block.header.parent_state_root)} does not match with working state {format_hash(self.working_state.state_root)}")
            raise BlockValidationError(BlockValidationErrorCode.state_root_mismatch)

        self.block_context.state_root = self.working_state.state_root

        # Set components pre-state
        pre_state_timeslot = self.working_state.timeslot
        pre_state_recent_history = self.working_state.recent_history
        pre_state_entropy = self.working_state.entropy
        pre_state_disputes = self.working_state.disputes
        pre_state_assurances = self.working_state.assurances
        pre_state_safrole = self.working_state.safrole
        pre_state_validator_pool = self.working_state.validator_pool
        pre_state_validator_archive = self.working_state.validator_archive
        pre_state_validator_queue = self.working_state.validator_queue
        pre_state_statistics = self.working_state.statistics
        pre_state_authorizer_queues = self.working_state.authorizer_queues
        pre_state_privileged_services = self.working_state.privileged_services
        pre_state_authorizer_pools = self.working_state.authorizer_pools
        pre_state_accumulation_history = self.working_state.accumulation_history
        pre_state_accumulation_queue = self.working_state.accumulation_queue
        pre_state_services = ServicesState(services={})

        # Set storage engine for services
        pre_state_services.set_state_storage(self.state_storage)
        pre_state_services.pending_changes = PendingChanges()

        # Validate quality of dispute extrinsic data
        self.components.disputes.validate_extrinsic_disputes(
            extrinsic_disputes=block.extrinsic.disputes,
            pre_state_timeslot=pre_state_timeslot,
            pre_state_validator_pool=pre_state_validator_pool,
            pre_state_validator_archive=pre_state_validator_archive
        )

        # Validate quality of preimage extrinsic data
        self.components.services.validate_extrinsic_preimages(
            extrinsic_preimages=block.extrinsic.preimages,
            pre_state_services=pre_state_services
        )

        # Validate quality of assurance extrinsic data
        self.components.assurances.validate_after_disputes(
            extrinsic_assurances=block.extrinsic.assurances,
            pre_state_validator_pool=pre_state_validator_pool,
            header=block.header
        )

        # Validator Pool STF Block Data | GP-0.5.0-eq:4.10
        validator_pool_output = self.components.validator_pool.state_transition(
            header=block.header,
            pre_state_timeslot=pre_state_timeslot,
            pre_state_validator_pool=pre_state_validator_pool,
            pre_state_safrole=pre_state_safrole
        )

        # Set H_a
        block.header.set_author_bandersnatch_key(post_state_validator_pool=validator_pool_output.post_state)

        # Timeslot STF Block Data | GP-0.5.0-eq:4.5
        timeslot_output = self.components.timeslot.state_transition(
            header=block.header
        )

        # RecentHistoryIntermediate STF Block Data | GP-0.5.0-eq:4.6
        recent_history_intermediate_output = self.components.recent_history.state_transition_intermediate(
            header=block.header,
            pre_state_recent_history=pre_state_recent_history
        )

        # Entropy STF Block Data | GP-0.5.0-eq:4.9
        entropy_output = self.components.entropy.state_transition(
            header=block.header,
            pre_state_timeslot=pre_state_timeslot,
            pre_state_entropy=pre_state_entropy
        )

        # Disputes STF Block Data | GP-0.5.0-eq:4.12
        disputes_output = self.components.disputes.state_transition(
            extrinsic_disputes=block.extrinsic.disputes,
            pre_state_disputes=pre_state_disputes
        )

        # Assurances After Disputes STF Block Data | GP-0.5.0-eq:4.13
        assurances_after_disputes_output = self.components.assurances.state_transition_after_disputes(
            extrinsic_disputes=block.extrinsic.disputes,
            pre_state_assurances=pre_state_assurances
        )

        # Validator Archive STF Block Data | GP-0.5.0-eq:4.11
        validator_archive_output = self.components.validator_archive.state_transition(
            header=block.header,
            pre_state_timeslot=pre_state_timeslot,
            pre_state_validator_archive=pre_state_validator_archive,
            pre_state_validator_pool=pre_state_validator_pool
        )

        # Safrole STF Block Data | GP-0.5.0-eq:4.8
        safrole_output = self.components.safrole.state_transition(
            header=block.header,
            pre_state_timeslot=pre_state_timeslot,
            extrinsic_tickets=block.extrinsic.tickets,
            pre_state_safrole=pre_state_safrole,
            pre_state_validator_queue=pre_state_validator_queue,
            post_state_entropy=entropy_output.post_state,
            post_state_validator_pool=validator_pool_output.post_state,
            post_state_disputes=disputes_output.post_state
        )

        # Validate quality of header data (second stage)

        if not produce:
            block_validation.validate_header_after_safrole(
                header=block.header,
                post_entropy=entropy_output.post_state,
                post_validator_pool=validator_pool_output.post_state,
                safrole_output=safrole_output,
                disputes_output=disputes_output,
                extrinsic=block.extrinsic
            )

        # Entropy STF Block Data | GP-0.7.1-eq:4.8
        # TODO second time is necessary because author bandersnatch key is known after
        entropy_output = self.components.entropy.state_transition(
            header=block.header,
            pre_state_timeslot=pre_state_timeslot,
            pre_state_entropy=pre_state_entropy
        )

        if produce:
            # Create marker data
            block.header.epoch_marker = safrole_output.epoch_mark
            block.header.tickets_marker = safrole_output.tickets_mark
            block.header.offenders_marker = disputes_output.offenders_mark

            # Create seal
            block.header.seal = self.generate_block_seal(
                block.header, safrole_output.post_state, entropy_output.post_state
            )

            # Update block hash
            self.state_storage.update_temporary_block_hash(block.header.hash)


        # Assurances After Assurances STF Block Data | GP-0.7.1-eq:4.13
        assurances_after_assurances_output = self.components.assurances.state_transition_after_assurances(
            extrinsic_assurances=block.extrinsic.assurances,
            intermediate_state_assurances_after_disputes=assurances_after_disputes_output.intermediate_state_after_disputes,
            header=block.header,
        )

        # GP-0.7.1-eq:11.16
        self.block_context.available_work_reports = assurances_after_assurances_output.reported

        # GP-0.7.1-eq:11.21
        self.block_context.set_guarantor_assignments(
            post_entropy=entropy_output.post_state,
            post_timeslot=timeslot_output.post_state,
            post_validator_pool=validator_pool_output.post_state,
        )

        # GP-0.7.1-eq:11.22
        self.block_context.set_prev_guarantor_assignments(
            post_entropy=entropy_output.post_state,
            post_timeslot=timeslot_output.post_state,
            post_validator_pool=validator_pool_output.post_state,
            post_validator_archive=validator_archive_output.post_state,
        )

        # Validate quality of guarantees extrinsic data
        self.components.assurances.validate_guarantees(
            extrinsic_guarantees=block.extrinsic.guarantees,
            pre_services_state=pre_state_services,
            intermediate_state_recent_history=recent_history_intermediate_output.intermediate_state,
            pre_authorizer_pools=pre_state_authorizer_pools,
            intermediate_state_assurances_after_assurances=assurances_after_assurances_output.intermediate_state_after_assurances,
            post_state_validator_pool=validator_pool_output.post_state,
            header=block.header,
            pre_accumulation_history=pre_state_accumulation_history,
            post_entropy=entropy_output.post_state,
            post_state_timeslot=timeslot_output.post_state,
            post_state_validator_archive=validator_archive_output.post_state,
            post_state_disputes=disputes_output.post_state
        )

        # Assurances After Guarantees STF Block Data | GP-0.7.1-eq:4.14
        assurances_output = self.components.assurances.state_transition_after_guarantees(
            extrinsic_guarantees=block.extrinsic.guarantees,
            intermediate_state_assurances_after_assurances=assurances_after_assurances_output.intermediate_state_after_assurances,
            pre_state_validator_pool=pre_state_validator_pool,
            post_state_timeslot=timeslot_output.post_state
        )

        # GP-0.7.1-eq:11.26
        self.block_context.reporters = assurances_output.reporters

        # GP-0.7.1-eq:12.4
        self.block_context.set_ready_work_reports()

        # GP-0.7.1-eq:12.5
        self.block_context.set_queued_work_reports(pre_state_accumulation_history)

        # GP-0.7.1-eq:12.10-12.12
        self.block_context.set_accumulatable_work_reports(
            header=block.header,
            accumulation_queue=pre_state_accumulation_queue
        )

        nr_acc_reports = len(self.block_context.accumulatable_work_reports)
        nr_queued_reports = max(0, len(self.block_context.queued_work_reports) - nr_acc_reports)

        if nr_queued_reports > 0:
            logging.info(f'📥 Accumulatable work-reports: {nr_acc_reports} ({nr_queued_reports} queued)')
        elif nr_acc_reports > 0:
            logging.info(f'📥 Accumulatable work-reports: {nr_acc_reports}')

        # Services Accumulation STF Block Data | GP-0.7.1-eq:4.18
        services_after_accumulation_output = await self.components.services.state_transition_accumulation(
            accumulatable_work_reports=self.block_context.accumulatable_work_reports,
            pre_state_privileged_services=pre_state_privileged_services,
            pre_state_services=pre_state_services,
            pre_state_validator_queue=pre_state_validator_queue,
            pre_state_authorizer_queues=pre_state_authorizer_queues,
            post_state_timeslot=timeslot_output.post_state,
            post_state_entropy=entropy_output.post_state
        )

        # Services After Preimages STF Block Data | GP-0.7.1-eq:4.18
        services_after_preimages_output = await self.components.services.state_transition_after_preimages(
            extrinsic_preimages=block.extrinsic.preimages,
            intermediate_state_after_accumulation=services_after_accumulation_output.intermediate_state_after_accumulation,
            post_state_timeslot=timeslot_output.post_state
        )

        # Statistics STF Block Data | GP-0.7.1-eq:4.20
        statistics_output = self.components.statistics.state_transition(
            extrinsic_guarantees=block.extrinsic.guarantees,
            extrinsic_preimages=block.extrinsic.preimages,
            extrinsic_assurances=block.extrinsic.assurances,
            extrinsic_tickets=block.extrinsic.tickets,
            pre_state_timeslot=pre_state_timeslot,
            post_state_timeslot=timeslot_output.post_state,
            post_state_validator_pool=validator_pool_output.post_state,
            pre_state_statistics=pre_state_statistics,
            header=block.header
        )

        # AuthorizerPools STF Block Data | GP-0.7.1-eq:4.19
        authorizer_pools_output = self.components.authorizer_pools.state_transition(
           header=block.header,
           extrinsic_guarantees=block.extrinsic.guarantees,
           post_state_authorizer_queues=services_after_accumulation_output.post_state_authorizer_queues,
           pre_state_authorizer_pools=pre_state_authorizer_pools
        )

        # RecentHistory STF Block Data | GP-0.7.1-eq:4.17
        recent_history_output = self.components.recent_history.state_transition(
           header=block.header,
           extrinsic_guarantees=block.extrinsic.guarantees,
           intermediate_state_recent_history=recent_history_intermediate_output.intermediate_state,
           beefy_commitment_map=services_after_accumulation_output.beefy_commitment_map
        )

        # Accumulation History STF | GP-0.6.1-eq:???
        # TODO: general review of this section after 0.7.1
        accumulation_history_output = self.components.accumulation_history.state_transition(
            accumulatable_work_reports=self.block_context.accumulatable_work_reports,
            pre_state_accumulation_history=pre_state_accumulation_history,
            nr_work_results_accumulated=services_after_accumulation_output.nr_work_results_accumulated
        )

        # Accumulation Queue STF | GP-0.6.1-eq:???
        # TODO: general review of this section after 0.7.1
        accumulation_queue_output = self.components.accumulation_queue.state_transition(
            queued_work_reports=self.block_context.queued_work_reports,
            pre_state_accumulation_queue=pre_state_accumulation_queue,
            post_state_accumulation_history=accumulation_history_output.post_state,
            pre_state_timeslot=pre_state_timeslot,
            post_state_timeslot=timeslot_output.post_state
        )

        # All state transitions successful, commit state changes
        self.working_state.timeslot = timeslot_output.post_state
        self.working_state.entropy = entropy_output.post_state
        self.working_state.disputes = disputes_output.post_state
        self.working_state.validator_pool = validator_pool_output.post_state
        self.working_state.validator_archive = validator_archive_output.post_state
        self.working_state.safrole = safrole_output.post_state
        self.working_state.assurances = assurances_output.post_state
        self.working_state.recent_history = recent_history_output.post_state
        self.working_state.authorizer_pools = authorizer_pools_output.post_state
        self.working_state.authorizer_queues = services_after_accumulation_output.post_state_authorizer_queues
        self.working_state.services = services_after_preimages_output.post_state
        self.working_state.statistics = statistics_output.post_state
        self.working_state.accumulation_queue = accumulation_queue_output.post_state
        self.working_state.accumulation_history = accumulation_history_output.post_state
        self.working_state.validator_queue = services_after_accumulation_output.post_state_validator_queue
        self.working_state.privileged_services = services_after_accumulation_output.post_state_privileged_services
        self.working_state.recent_accumulation_outputs = services_after_accumulation_output.beefy_commitment_map

        await self.store_jam_state()

        self.state_storage.commit()

        self.working_state.state_root = self.state_storage.state_root()

        return STFOutput(
            epoch_mark=safrole_output.epoch_mark,
            tickets_mark=safrole_output.tickets_mark,
            offenders_mark=disputes_output.offenders_mark
        )

    @log_execution_time
    async def add_ancestor_block(self, block: Block):

        await self.add_ancestor_header(block.header)

        await self.store_block(block)

        if self.pubsub:
            await self.pubsub.publish(PubSubSignal(topic=MESSAGE_TYPES.BEST_BLOCK, data=block))
            await self.pubsub.publish(PubSubSignal(topic=MESSAGE_TYPES.FINALIZED_BLOCK, data=block))  # TODO: placeholder for now, move when implemented
            await self.pubsub.publish(PubSubSignal(topic=MESSAGE_TYPES.STATISTICS, data=self.working_state.statistics.to_jam_bytes().to_bytes()))

    @log_execution_time
    async def add_ancestor_header(self, header: Header):
        DEBUG and logging.debug(f"Addded ancestor_header: {format_hash(header.hash)}")
        # Add header to ancestors
        self.state_storage.add_ancestor(header)

    @log_execution_time
    async def _import_block(self, block: Block, dry_run=False) -> STFOutput:

        output = await self.state_transition(block, produce=False)

        await self.add_ancestor_block(block)

        return output

    async def store_block(self, block: Block):
        # Store block in DB
        self.block_db.put(
            b'block:' + block.header.timeslot.to_bytes(length=4, byteorder='little'), block.to_jam_bytes().to_bytes()
        )

        await self.store_block_header(block.header)

    async def store_block_header(self, header: Header):

        self.block_db.put(
            b'block_header:' + header.hash, header.to_jam_bytes().to_bytes()
        )

        self.block_db.put(
            b'block_hash:' + header.timeslot.to_bytes(length=4, byteorder='little'), header.hash
        )
        self.block_db.put(
            b'block_number:' + header.hash, header.timeslot.to_bytes(length=4, byteorder='little')
        )

    def retrieve_block(self, timeslot: int) -> Optional[Block]:
        block_data = self.block_db.get(b'block:' + timeslot.to_bytes(length=4, byteorder='little'))
        if block_data is not None:
            return Block.from_jam_bytes(JamBytes(block_data))

    def retrieve_block_by_hash(self, block_hash: bytes) -> Optional[Block]:
        timeslot_data = self.block_db.get(b'block_number:' + block_hash)
        if timeslot_data is not None:
            block_data = self.block_db.get(b'block:' + timeslot_data)
            if block_data is not None:
                return Block.from_jam_bytes(JamBytes(block_data))

    def retrieve_block_header(self, block_hash: bytes) -> Optional[Header]:
        header_data = self.block_db.get(b'block_header:' + block_hash)
        if header_data is not None:
            return Header.from_jam_bytes(JamBytes(header_data))
        return None

    def retrieve_finalized_head(self) -> bytes:
        return self.block_db.get(b'finalized_head')

    async def store_finalized_head(self, block_hash: bytes):
        return self.block_db.put(b'finalized_head', block_hash)

    def retrieve_block_hash(self, timeslot: int) -> Optional[bytes]:
        return self.block_db.get(b'block_hash:' + timeslot.to_bytes(length=4, byteorder='little'))

    def should_produce_block(self, timeslot: int, safrole_state: SafroleState) -> bool:
        slot_phase_index = timeslot % EPOCH_TIMESLOTS

        if not self.config.keys:
            # Cannot produce without validator keys
            # TODO keys should always exist and explicit make --validator option
            return False

        # Check if seal-key series is fallback
        if safrole_state.slot_sealer_series.tickets is not None:
            # Retrieve current ticket
            ticket_id = safrole_state.slot_sealer_series.tickets[slot_phase_index].id
            should_produce = ticket_id in self.block_extrinsic.own_tickets_current

            if should_produce:
                DEBUG and logging.debug(f'Owning ticket ID: {ticket_id.hex()}')
            else:
                DEBUG and logging.debug(f'Waiting for author with ticket ID: {ticket_id.hex()}')

            return should_produce

        elif safrole_state.slot_sealer_series.keys is not None:
            author = safrole_state.slot_sealer_series.keys[slot_phase_index]

            should_produce = author == self.config.keys.bandersnatch.public_key

            if should_produce:
                DEBUG and logging.debug(f'Having author key: {author.hex()}')
            else:
                DEBUG and logging.debug(f'Waiting for author with key: {author.hex()}')

            return should_produce

        return False

    def get_block_seal_vrf_input(
            self,
            timeslot: int,
            safrole_state: SafroleState,
            entropy_state: EntropyState
    ) -> bytes:
        """
        Get relevant seal VRF input (ticket or fallback)

        Returns
        -------
        bytes
        """
        if safrole_state.slot_sealer_series.tickets is not None:

            ticket = safrole_state.slot_sealer_series.tickets[self.slot_phase_index(timeslot)]
            DEBUG and logging.debug(f"VRF input: for ticket {ticket.id.hex()} with entropy {entropy_state.entropy[3].hex()}")
            return vrf_input_ticket_seal(bytes(entropy_state.entropy[3]), ticket.attempt)

        elif safrole_state.slot_sealer_series.keys is not None:
            DEBUG and logging.debug(f"VRF input: Fallback with entropy {entropy_state.entropy[3].hex()}")
            return vrf_input_fallback_seal(bytes(entropy_state.entropy[3]))

        else:
            raise PyjamazAppError("No valid sealing policy in current state")

    def generate_block_seal(self, header: Header, safrole_state: SafroleState, entropy_state: EntropyState) -> bytes:
        """
        GP-0.7.1-eq:6.15,6.16 (bold_H_s) | Generate block seal

        Parameters
        ----------
        header: Header
        safrole_state: SafroleState
        entropy_state: EntropyState

        Returns
        -------
        bytes
        """

        if safrole_state.slot_sealer_series.tickets is not None:

            ticket = safrole_state.slot_sealer_series.tickets[self.slot_phase_index(header.timeslot)]
            DEBUG and logging.debug(f"Ticket Seal for ticket {ticket.id.hex()} with entropy {entropy_state.entropy[3].hex()}")

            return header.generate_ticket_seal(
                bandersnatch_priv_key=self.config.keys.bandersnatch.private_key,
                entropy=bytes(entropy_state.entropy[3]),
                ticket_attempt=ticket.attempt
            )

        elif safrole_state.slot_sealer_series.keys is not None:
            DEBUG and logging.debug(f"Fallback Seal with entropy {entropy_state.entropy[3].hex()}")
            return header.generate_fallback_seal(
                bandersnatch_priv_key=self.config.keys.bandersnatch.private_key,
                entropy=bytes(entropy_state.entropy[3])
            )

        else:
            raise PyjamazAppError("No valid sealing policy in current state")

    def generate_entropy_source(self, timeslot: int, safrole_state: SafroleState, entropy_state: EntropyState) -> bytes:
        """
        GP-0.7.1-eq:6.17 (bold_H_v) | Generate entropy source

        Parameters
        ----------
        timeslot
        safrole_state
        entropy_state

        Returns
        -------
        bytes
        """
        self.block_context.seal_vrf_output = self.config.keys.bandersnatch.vrf_output(
            self.get_block_seal_vrf_input(timeslot, safrole_state, entropy_state)
        )
        DEBUG and logging.debug(f"Entropy source generated with: bs_pub={self.config.keys.bandersnatch.public_key.hex()} seal_vrf={self.block_context.seal_vrf_output.hex()} ")
        return ietf_vrf_sign(
            self.config.keys.bandersnatch.private_key,
            b"jam_entropy" + self.block_context.seal_vrf_output,
            b""
        )

    def current_timeslot(self) -> int:
        return int(time.time() - self.config.common_era) // SLOT_PERIOD

    def slot_phase_index(self, timeslot: int) -> int:
        """
        Block Data | GP-0.7.1-eq:6.2 (m) | Function that returns the phase index into the epoch of the timeslot

        Returns
        -------
        number: int
            Phase index into the epoch of the timeslot

        """
        return timeslot % EPOCH_TIMESLOTS

    def get_next_slot_timestamp(self) -> int:
        elapsed_timeslots = (time.time() - self.config.common_era) // SLOT_PERIOD
        return self.config.common_era + (elapsed_timeslots + 1) * SLOT_PERIOD

    def get_author_index(self, safrole_post_state: SafroleState = None) -> int:
        """
        Get the author index for current node in the current validator set

        Block Data | GP-0.7.1-eq:5.9

        Parameters
        ----------

        Returns
        -------
        int
        """
        if safrole_post_state is None:
            safrole_post_state = self.working_state.safrole

        for index, validator in enumerate(safrole_post_state.validators):
            if validator.bandersnatch == self.config.keys.bandersnatch.public_key:
                return index
        raise BlockValidationError(f"Bandersnatch {self.config.keys.bandersnatch.public_key} not found in current validator set")

    def get_validator_index(self) -> Optional[int]:
        """
        Get the validator index for current node in the validator pool
        """
        for index, validator in enumerate(self.working_state.validator_pool.validators):
            if validator.bandersnatch == self.config.keys.bandersnatch.public_key:
                return index
        return None

    async def produce_block(
            self, timeslot: int, parent_header_hash: bytes, safrole_state: SafroleState, entropy_state: EntropyState
    ) -> Block:

        if timeslot % EPOCH_TIMESLOTS > 0:
            entropy = entropy_state.entropy[2]

            if not SOLO_MODE and self.block_extrinsic.can_add_own_ticket(timeslot):

                ring_public_keys = [v.bandersnatch for v in safrole_state.validators]
                ring_context = RingContext(self.config.ring_data, ring_public_keys)

                self.block_extrinsic.add_own_ticket(
                    ring_context, entropy, self.config.keys.bandersnatch, self.get_author_index()
                )

                self.block_extrinsic.add_own_ticket(
                    ring_context, entropy, self.config.keys.bandersnatch, self.get_author_index()
                )

                self.block_extrinsic.add_own_ticket(
                    ring_context, entropy, self.config.keys.bandersnatch, self.get_author_index()
                )

        extrinsic = Extrinsic(
            tickets=self.block_extrinsic.collect_tickets(),
            disputes=ExtrinsicDisputes(verdicts=[], culprits=[], faults=[]),
            preimages=self.block_extrinsic.collect_preimages(self.working_state.services),
            assurances=self.block_extrinsic.collect_assurances(),
            guarantees=self.block_extrinsic.collect_guarantees(),
        )

        header = Header(
            parent=parent_header_hash,
            parent_state_root=self.working_state.state_root,
            extrinsic_hash=extrinsic.generate_extrinsic_hash(),
            timeslot=timeslot,
            # Placeholder
            epoch_marker=None,
            # Placeholder
            tickets_marker=None,
            # Placeholder
            offenders_marker=[],
            # Placeholder
            author_index=self.get_author_index(safrole_state),
            entropy_source=self.generate_entropy_source(timeslot, safrole_state, entropy_state),
            # Placeholder
            seal=bytes(96)
        )

        DEBUG and logging.debug(f"Produced with parent: {header.parent.hex()}")

        block = Block(
            header=header,
            extrinsic=extrinsic
        )

        if self.config.create_traces:
            pre_state = await self.create_state_dump()

        await self.state_transition(block, produce=True)

        await self.add_ancestor_block(block)

        DEBUG and logging.debug(f'New state root: {format_hash(self.working_state.state_root)}')

        if self.config.create_traces:
            await self.store_trace(pre_state, block, self.config.create_traces)

        return block

    async def finalize(self, header_hash: bytes):
        if header_hash != self.state_storage.finalized_block_hash:
            self.state_storage.finalize(header_hash)
            await self.store_finalized_head(header_hash)
            logging.info(f'🔒 Finalized block  {format_hash(header_hash)}')
        else:
            DEBUG and logging.debug(f'Skipped finalization, {format_hash(header_hash)} already finalized')

    async def create_state_dump(self) -> StateDump:
        return StateDump(
            state_root=self.working_state.state_root,
            keyvals=[(k, v) for k, v in self.state_db.as_list()]
        )

    async def store_trace(self, pre_state: StateDump, block: Block, traces_dir: str):

        base_filename = f'{block.header.timeslot:08}'

        post_state = await self.create_state_dump()

        trace = Trace(
            pre_state=pre_state,
            block=block,
            post_state=post_state
        )

        with open(os.path.join(traces_dir, f'{base_filename}.json'), 'w') as file:
            json.dump(trace.to_json(), file, indent=2)

        with open(os.path.join(traces_dir, f'{base_filename}.bin'), 'wb') as file:
            file.write(trace.to_jam_bytes().to_bytes())

        logging.info(f"💾 successfully stored trace data {base_filename}.bin")

    def get_beefy_root(self, header_hash: bytes = None) -> Optional[bytes]:

        if len(self.working_state.recent_history.recent_blocks) == 0:
            return bytes(32)

        for block in reversed(self.working_state.recent_history.recent_blocks):
            if header_hash is None or block.header_hash == header_hash:
                return block.beefy_root

        return None

    # TODO move refine function?
    def get_core_assigment(self) -> Optional[int]:
        if self.block_context.guarantor_assignments:
            for assignment in self.block_context.guarantor_assignments:
                if assignment.validator_ed25519 == self.config.keys.ed25519.public_key:
                    return assignment.core_index
        return None

    def get_other_guarantors(self):
        core_assignment = self.get_core_assigment()
        guarantors = []
        for assignment in self.block_context.guarantor_assignments:
            if assignment.validator_ed25519 != self.config.keys.ed25519.public_key and assignment.core_index != core_assignment:
                guarantors.append(assignment.validator_ed25519)
        return guarantors

    def add_work_package(self, work_package: WorkPackage, extrinsics: List[bytes]):

        self.work_package_queue[work_package.hash()] = WorkPackageQueueItem(work_package=work_package, status=WorkPackageStatus(Reportable=WorkPackageReportableStatus(remaining_blocks=4)))

        self.work_package_extrinsics.add(work_package, extrinsics)

        logging.info(f"📥 Added work package to queue: {format_hash(work_package.hash())}")

    def add_work_package_bundle(self, work_package_bundle: WorkPackageBundle):

        self.add_work_package(work_package_bundle.work_package, work_package_bundle.extrinsic_data)


    async def process_work_package(self, work_package: WorkPackage) -> WorkReport:
        if self.get_core_assigment() is None:
            raise ProcessWorkpackageError("Cannot process work package: no core assignment")

        # Prepare extrinsic data (GP-0.7.1-eq:B.6 bold_x_flat)
        extrinsics = [
            [self.work_package_extrinsics.get(work_package, x.hash, x.len) for x in w.extrinsic]
            for w in work_package.items
        ]

        # Set code
        work_package.set_authorization_code(self.working_state.services)
        work_report = await self.work_result_computation(
            work_package=work_package,
            core_index=self.get_core_assigment(),
            services_state=self.working_state.services,
            extrinsics=extrinsics
        )
        # Clean up work package extrinsics
        self.work_package_extrinsics.clear(work_package)
        DEBUG and logging.debug(f"Processed work package: {format_hash(work_package.hash())}")
        return work_report

    async def guarantee_work_report(self, work_report: WorkReport, timeslot: int):

        credential = await self.create_guarantee_signature(work_report)

        guarantee = Guarantee(
            report=work_report,
            slot=timeslot,
            signatures=[
                credential
            ]
        )

        # TODO exchange signature with other validators
        for v_idx, assignment in enumerate(self.block_context.guarantor_assignments):
            if assignment.validator_ed25519 != self.config.keys.ed25519.public_key and assignment.core_index == self.get_core_assigment():
                guarantee.signatures.append(await self.create_guarantee_signature_for_validator(work_report, v_idx))

        self.block_extrinsic.add_guarantee(guarantee)

    async def create_guarantee_signature(self, work_report: WorkReport) -> Credential:
        payload = b"jam_guarantee" + blake2b_256_hash(work_report.to_jam_bytes().to_bytes())
        signature = self.config.keys.ed25519.sign(payload)

        return Credential(
            validator_index=self.get_author_index(),
            signature=signature
        )

    # TODO temp function
    async def create_guarantee_signature_for_validator(self, work_report: WorkReport, validator_index: int) -> Credential:
        payload = b"jam_guarantee" + blake2b_256_hash(work_report.to_jam_bytes().to_bytes())

        validator_keys = Keys.from_seed(validator_index.to_bytes(4, 'little') * 8)

        signature = validator_keys.ed25519.sign(payload)

        return Credential(
            validator_index=validator_index,
            signature=signature
        )

    def create_assurance(self, cores: List[int]) -> Assurance:
        bitfield = [False] * CORE_COUNT
        anchor = self.retrieve_block_hash(self.working_state.timeslot.number) # TODO keep current block hash in block_context?

        for core in cores:
            bitfield[core] = True

        bitfield_bytes = BitArray(CORE_COUNT).encode(bitfield).to_bytes()

        sign_payload = b"jam_available" + blake2b_256_hash(anchor + bitfield_bytes)

        signature = self.config.keys.ed25519.sign(sign_payload)

        return Assurance(
            anchor=anchor,
            bitfield=bitfield,
            signature=signature,
            validator_index=self.get_validator_index()
        )

    def create_assurance_for_validator_index(self, cores: List[int], validator_index: int) -> Assurance:
        """
        TODO temp function for SOLO_MODE
        """
        bitfield = [False] * CORE_COUNT
        anchor = self.retrieve_block_hash(self.working_state.timeslot.number)  # TODO keep current block hash in block_context?

        for core in cores:
            bitfield[core] = True

        bitfield_bytes = BitArray(CORE_COUNT).encode(bitfield).to_bytes()

        sign_payload = b"jam_available" + blake2b_256_hash(anchor + bitfield_bytes)

        validator_keys = Keys.from_seed(validator_index.to_bytes(4, 'little') * 8)
        signature = validator_keys.ed25519.sign(sign_payload)

        return Assurance(
            anchor=anchor,
            bitfield=bitfield,
            signature=signature,
            validator_index=validator_index
        )


    async def process_refine(self, timeslot: int) -> Optional[WorkReport]:
        """
        Process queued work packages and guarantee work reports.
        """

        wp_queue_item = None
        cleanup_queue = []

        # Clean up work packages
        for h, w in self.work_package_queue.items():
            if not self.working_state.recent_history.get_recent_block(w.work_package.context.lookup_anchor):
                cleanup_queue.append(h)

        for h in cleanup_queue:
            del self.work_package_queue[h]
            logging.info(f"🗑️ Discarded outdated work package {format_hash(h)}")

        # Find first authorized work package
        for h, w in self.work_package_queue.items():
            if w.status.enum_value()[0] == 'Reportable':
                if self.working_state.authorizer_pools.is_authorized(w.work_package, self.get_core_assigment()):
                    wp_queue_item = self.work_package_queue[h]
                    break

        if wp_queue_item is None:
            # No reportable work package found, return
            return None

        try:
            work_report = await self.process_work_package(wp_queue_item.work_package)
            # Update WorkPackage status
            wp_queue_item.status = WorkPackageStatus(Reported=WorkPackageReportedStatus(
                reported_in=BlockDesc(
                    slot=self.working_state.timeslot.number,
                    header_hash=self.retrieve_block_hash(self.working_state.timeslot.number)
                ),
                core=self.get_core_assigment(),
                report_hash=work_report.hash()
            ))
            if self.app_context.pubsub:
                # Send signal
                await self.app_context.pubsub.publish(
                    PubSubSignal(
                        topic=MESSAGE_TYPES.WORK_PACKAGE_STATUS,
                        data=[wp_queue_item.status.to_json()]
                    )
                )
            await self.guarantee_work_report(work_report, timeslot)
            return work_report

        except ProcessWorkpackageError as e:
            # Update WorkPackage status
            wp_queue_item.status = WorkPackageStatus(Failed=str(e))
            if self.app_context.pubsub:
                await self.app_context.pubsub.publish(
                    PubSubSignal(
                        topic=MESSAGE_TYPES.WORK_PACKAGE_STATUS,
                        data=[wp_queue_item.status.to_json()]
                    )
                )
            logging.error(f"Error processing work package {format_hash(wp_queue_item.work_package.hash())}: {e}")
            return None

    async def work_result_computation(
        self,
        work_package: WorkPackage,
        core_index: int,
        services_state: ServicesState,
        extrinsics: List[List[bytes]]
) -> WorkReport:
        """
        GP-0.7.2-eq:14.12 (function Ξ) | the work result computation function.

        TODO finish
        """

        segment_root_lookup_keys = {h for w in work_package.items for (h, n) in w.import_segments}

        # Collect import segments
        import_segments = [self.segment_store.get(r) for r in segment_root_lookup_keys]

        auth_output = pvm_invoke_is_authorized(work_package, core_index)

        if type(auth_output.work_exec_result.ok) is not bytes:
            raise ProcessWorkpackageError("Unauthorized")

        if len(auth_output.work_exec_result.ok) > MAXIMUM_SIZE_ENCODED_WORK_REPORT:
            raise ProcessWorkpackageError("Oversized auth result")

        refine_outputs: List[Tuple[WorkDigest, List[bytes]]] = []

        total_digest_size = len(auth_output.work_exec_result.ok)

        for j in range(len(work_package.items)):

            work_item = work_package.items[j]

            export_segment_offset = sum([w.export_count for k, w in enumerate(work_package.items) if k < j])

            refine_output = pvm_invoke_refine(
                core_index=core_index,
                work_item_index=j,
                work_package=work_package,
                authorizer_output=auth_output.work_exec_result.ok,
                work_items_import_segments=import_segments,
                export_segment_offset=export_segment_offset,
                services_state=services_state,
                extrinsics=extrinsics
            )

            if total_digest_size + len(refine_output.work_exec_result.ok or b'') > MAXIMUM_SIZE_ENCODED_WORK_REPORT:
                work_exec_result = WorkExecResult(digest_oversize=True)
                export_segments = [bytes(EC_SEGMENT_SIZE)] * len(refine_output.export_segments)

            elif len(refine_output.export_segments) != work_item.export_count:
                work_exec_result = WorkExecResult(bad_exports=True)
                export_segments = [bytes(EC_SEGMENT_SIZE)] * len(refine_output.export_segments)

            elif refine_output.work_exec_result.ok is None:
                work_exec_result = refine_output.work_exec_result
                export_segments = [bytes(EC_SEGMENT_SIZE)] * len(refine_output.export_segments)

            else:
                work_exec_result = refine_output.work_exec_result
                export_segments = refine_output.export_segments
                total_digest_size += len(refine_output.work_exec_result.ok)

            work_result = WorkDigest.from_work_item(
                work_item=work_package.items[j],
                result=work_exec_result,
                gas_used=refine_output.gas_used
            )

            refine_outputs.append((work_result, export_segments))

        # TODO inefficient: refactor refine_outputs to work_results and all_export_segments ?
        all_export_segments = flatten_list([o[1] for o in refine_outputs])

        exports_root = ConstantDepthMerkleTree(all_export_segments).root()

        # store segments
        self.segment_store[exports_root] = all_export_segments
        # Also store under work-package hash
        self.segment_store[work_package.hash()] = all_export_segments

        package_spec = WorkPackageSpec.create_from_work_package(work_package, [], [], [], all_export_segments)

        return WorkReport(
            package_spec=package_spec,
            context=work_package.context,
            core_index=core_index,
            authorizer_hash=work_package.authorizer_hash(),
            auth_output=auth_output.work_exec_result.ok,
            segment_root_lookup={}, # TODO
            results=[o[0] for o in refine_outputs],
            auth_gas_used=auth_output.gas_used
        )

    async def process_assurances(self):
        """
        Check for active assignments and create assurances
        TODO finish naive implementation
        """
        for core_index, assignment in enumerate(self.working_state.assurances.assurances):
            if assignment is not None:
                # create assurance extrinsic
                assurance = self.create_assurance([core_index])
                self.block_extrinsic.add_assurance(assurance)

                # TODO temp SOLO mode
                if SOLO_MODE:
                    for val_idx in [i for i in range(6) if i != self.get_validator_index()]:
                        assurance = self.create_assurance_for_validator_index([core_index], val_idx)
                        self.block_extrinsic.add_assurance(assurance)

    def get_best_header_hash(self):
        return self.working_state.recent_history.recent_blocks[-1].header_hash


class StateComponents:

    def __init__(
            self,
            config: AppConfig,
            block_context: BlockContext,
            app_context: AppContext
    ):

        self.timeslot = Timeslot(block_context, app_context)
        self.recent_history = RecentHistory(block_context, app_context)
        self.entropy = Entropy(block_context, app_context)
        self.disputes = Disputes(block_context, app_context)
        self.assurances = Assurances(block_context, app_context)
        self.validator_archive = ValidatorArchive(block_context, app_context)
        self.validator_pool = ValidatorPool(block_context, app_context)
        self.safrole = Safrole(block_context, app_context, config.ring_data)
        self.validator_queue = ValidatorQueue(block_context, app_context)
        self.statistics = Statistics(block_context, app_context)
        self.services = Services(block_context, app_context)
        self.authorizer_queues = AuthorizerQueues(block_context, app_context)
        self.privileged_services = PrivilegedServices(block_context, app_context)
        self.authorizer_pools = AuthorizerPools(block_context, app_context)
        self.accumulation_queue = AccumulationQueue(block_context, app_context)
        self.accumulation_history = AccumulationHistory(block_context, app_context)
        self.recent_accumulation_output = RecentAccumulationLog(block_context, app_context)
