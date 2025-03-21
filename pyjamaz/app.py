import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from functools import partial
from typing import TypeVar, Optional, List, Callable

from bandersnatch_vrfs import ietf_vrf_sign

from jamcodec.base import JamBytes
from jamcodec.mixins import Serializable
from jamcodec.types import Vec

from pyjamaz.exceptions import PyjamazAppError
from pyjamaz.extrinsic import ExtrinsicAccumulator
from pyjamaz.graypaper_constants import MAXIMUM_AUTHORIZATION_QUEUE_ITEMS, CORE_COUNT, EPOCH_TIMESLOTS, \
    SLOT_PERIOD, MAXIMUM_AGE_LOOKUP_ANCHOR
from pyjamaz.merkle import PatriciaMerkleTrie
from pyjamaz.models.trace import StateDump, Trace
from pyjamaz.signing import Ed25519Keypair, BandersnatchKeypair
from pyjamaz.state.base import AppContext
from pyjamaz.storage import StorageEngine, Transaction

from pyjamaz.state.components import Timeslot, Entropy, Safrole, ValidatorArchive, ValidatorPool, ValidatorQueue, \
    RecentHistory, Disputes, Assurances, Statistics, PrivilegedServices, AuthorizerQueues, AuthorizerPools, Services, \
    AccumulationQueue, AccumulationHistory
from pyjamaz.models.block import Block, Header, Extrinsic, ExtrinsicDisputes, TicketEnvelope, BlockContext
from pyjamaz.models.state import JamState, ServicesState, AuthorizerQueuesState, SafroleState, EntropyState
from pyjamaz.models.stf_output import STFOutput
from pyjamaz.utils import vrf_input_fallback_seal, vrf_input_ticket_seal
from pyjamaz.validation import BlockValidation

T = TypeVar('T')


@dataclass
class Keys(Serializable):
    bandersnatch: BandersnatchKeypair = field(metadata={'codec': BandersnatchKeypair.to_codec_def()})
    ed25519: 'Ed25519Keypair' = field(metadata={'codec': Ed25519Keypair.to_codec_def()})

    @classmethod
    def from_seed(cls, seed: bytes) -> 'Keys':
        return cls(
            bandersnatch=BandersnatchKeypair.from_seed(seed),
            ed25519=Ed25519Keypair.from_private_key(seed)
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

        self.block_context = BlockContext()
        self.app_context = AppContext()

        self.import_lock = asyncio.Lock()

        self.components = StateComponents(
            storage_engine=self.state_db,
            config=self.config,
            block_context=self.block_context,
            app_context=self.app_context
        )

        self.extrinsic = ExtrinsicAccumulator(self.config.ring_data)

        self.state: Optional[JamState] = None
        self.state_trie_root = bytes(32)

        # Note:
        # For the import block function, we allow the option to provide a custom function (for example to augment with
        # traces or other debug info)
        if import_block_callback:
            self.import_block = partial(import_block_callback, self)
        else:
            self.import_block = self._import_block


    async def import_block_from_bytes(self, data):
        block = Block.from_jam_bytes(JamBytes(data))
        logging.debug(f"📦 Importing block {block.header.timeslot} from bytes")
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
            logging.info(f"Syncing in progress, current timeslot={self.state.timeslot.number}")


    async def import_block_from_json(self, data):
        logging.debug(f"📦 Importing block from json")
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
            if self.state.timeslot.number >= block.header.timeslot:
                logging.debug(f" TEMP BREAK block from process_import_queue: {block.header.timeslot}")
                continue

            await self.import_block(block)
            logging.debug(f'✅ Block {block.header.timeslot} succesfully imported from process_import_queue.')


    async def initialize(self):
        logging.debug("Retrieving state..")
        self.state = self.retrieve_jam_state()
        logging.debug("Updating state trie..")
        await self.update_state_trie()
        logging.debug("Retrieving ancestor headers..")
        self.block_context.ancestor_headers = self.retrieve_ancestor_headers()

    def retrieve_ancestor_headers(self) -> List[Header]:
        ancestor_headers = []
        best_block_hash = self.retrieve_block_hash(self.state.timeslot.number)
        if best_block_hash:
            header = self.retrieve_block_header(best_block_hash)
            ancestor_headers.append(header)
            for i in range(MAXIMUM_AGE_LOOKUP_ANCHOR):
                header = self.retrieve_block_header(header.parent)
                if header:
                    ancestor_headers.append(header)
                else:
                    break

        return ancestor_headers


    def retrieve_jam_state(self):
        return JamState(
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
            accumulation_history=self.components.accumulation_history.retrieve_state()
        )

    async def store_jam_state(self, state: JamState, transaction: Optional[Transaction] = None):
        self.components.timeslot.store_state(state.timeslot, transaction)
        self.components.recent_history.store_state(state.recent_history, transaction)
        self.components.entropy.store_state(state.entropy, transaction)
        self.components.disputes.store_state(state.disputes, transaction)
        self.components.assurances.store_state(state.assurances, transaction)
        self.components.validator_archive.store_state(state.validator_archive, transaction)
        self.components.validator_queue.store_state(state.validator_queue, transaction)
        self.components.validator_pool.store_state(state.validator_pool, transaction)
        self.components.safrole.store_state(state.safrole, transaction)
        self.components.statistics.store_state(state.statistics, transaction)
        #self.components.services.store_state(state.services, transaction)
        self.components.authorizer_queues.store_state(state.authorizer_queues, transaction)
        self.components.privileged_services.store_state(state.privileged_services, transaction)
        self.components.authorizer_pools.store_state(state.authorizer_pools, transaction)
        self.components.accumulation_queue.store_state(state.accumulation_queue, transaction)
        self.components.accumulation_history.store_state(state.accumulation_history, transaction)



    async def update_state_trie(self):
        """
        Updated the Patricia state trie.

        TODO create separate DB and only update affected branches for performance; now the whole state have to be
          in memory
        """
        state_trie = PatriciaMerkleTrie(list(self.state_db))
        self.state_trie_root = state_trie.root()

    def is_epoch_change(self, slotnumber: int = None) -> bool:
        """
        GP-0.5.0-general: `e!=e' ? T, F` | Helper function that determines if the epoch has changed.

        Returns
        -------
        bool
            `True` when epoch has changed, `False` otherwise.

        TODO duplicate code, move to dedicated package?
        """
        if slotnumber is None:
            slotnumber = self.current_timeslot()

        return self.state.timeslot.number // EPOCH_TIMESLOTS != slotnumber // EPOCH_TIMESLOTS

    async def state_transition(self, block: 'Block', transaction: Transaction, dry_run=False) -> 'STFOutput':
        """
        GP-0.5.0-eq:4.1 (Υ, σ') | Block Level State Transition Function for the JAM state.

        Implicit first parameter (self) | Current State | GP-0.5.0-eq:4.1 (σ)

        Parameters
        ----------
        block: Block
            Block Data | GP-0.5.0-eq:4.1 (bold_B)
        transaction: Transaction
        dry_run: bool

        Returns
        ----------
        STFOutput
        """

        # Reset block context
        self.block_context.reset()
        self.block_context.state_root = self.state_trie_root

        # Update app context
        self.app_context.transaction = transaction

        # Set up validation
        block_validation = BlockValidation(self.block_context)

        # Set components pre-state
        # TODO move deepcopy() from STF to here
        pre_state_timeslot = self.state.timeslot
        pre_state_recent_history = self.state.recent_history
        pre_state_entropy = self.state.entropy
        pre_state_disputes = self.state.disputes
        pre_state_assurances = self.state.assurances
        pre_state_safrole = self.state.safrole
        pre_state_validator_pool = self.state.validator_pool
        pre_state_validator_archive = self.state.validator_archive
        pre_state_validator_queue = self.state.validator_queue
        pre_state_statistics = self.state.statistics
        pre_state_authorizer_queues = self.state.authorizer_queues
        pre_state_privileged_services = self.state.privileged_services
        pre_state_authorizer_pools = self.state.authorizer_pools
        pre_state_accumulation_history = self.state.accumulation_history
        pre_state_accumulation_queue = self.state.accumulation_queue
        pre_state_services = self.state.services

        # Set storage engine for services
        pre_state_services.set_storage_engine(self.state_db) # TODO remove
        pre_state_services.set_storage_transaction(transaction)

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

        # Validator Pool STF Block Data | GP-0.5.0-eq:4.10
        validator_pool_output = self.components.validator_pool.state_transition(
            header=block.header,
            pre_state_timeslot=pre_state_timeslot,
            pre_state_validator_pool=pre_state_validator_pool,
            pre_state_safrole=pre_state_safrole
        )

        if not dry_run:
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

        # Validate quality of assurance extrinsic data
        self.components.assurances.validate_after_disputes(
            extrinsic_assurances=block.extrinsic.assurances,
            post_state_validator_pool=validator_pool_output.post_state,
            header=block.header
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

        if not dry_run:
            # Validate quality of header data
            # TODO location in STF?
            block_validation.validate_header(
                header=block.header,
                pre_state_timeslot=pre_state_timeslot,
                post_entropy=entropy_output.post_state,
                post_validator_pool=validator_pool_output.post_state,
                post_safrole=safrole_output.post_state,
                extrinsic=block.extrinsic
            )

        # Entropy STF Block Data | GP-0.5.0-eq:4.9
        # TODO second time is necessary because author bandersnatch key is known after
        entropy_output = self.components.entropy.state_transition(
            header=block.header,
            pre_state_timeslot=pre_state_timeslot,
            pre_state_entropy=pre_state_entropy
        )

        # Assurances After Assurances STF Block Data | GP-0.5.0-eq:4.14
        assurances_after_assurances_output = self.components.assurances.state_transition_after_assurances(
            extrinsic_assurances=block.extrinsic.assurances,
            intermediate_state_assurances_after_disputes=assurances_after_disputes_output.intermediate_state_after_disputes,
        )

        # GP-0.6.1-eq:11.16
        self.block_context.available_work_reports = assurances_after_assurances_output.reported

        # GP-0.6.1-eq:11.21
        self.block_context.set_guarantor_assignments(
            post_entropy=entropy_output.post_state,
            post_timeslot=timeslot_output.post_state,
            post_validator_pool=validator_pool_output.post_state,
        )

        # GP-0.6.1-eq:11.22
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
            post_state_validator_archive=validator_archive_output.post_state
        )

        # Assurances After Guarantees STF Block Data | GP-0.5.0-eq:4.15
        assurances_output = self.components.assurances.state_transition_after_guarantees(
            extrinsic_guarantees=block.extrinsic.guarantees,
            intermediate_state_assurances_after_assurances=assurances_after_assurances_output.intermediate_state_after_assurances,
            pre_state_validator_pool=pre_state_validator_pool,
            post_state_timeslot=timeslot_output.post_state
        )

        # GP-0.6.1-eq:11.26
        self.block_context.reporters = assurances_output.reporters

        # Statistics STF Block Data | GP-0.5.0-eq:4.20
        statistics_output = self.components.statistics.state_transition(
            extrinsic_guarantees=block.extrinsic.guarantees,
            extrinsic_preimages=block.extrinsic.preimages,
            extrinsic_assurances=block.extrinsic.assurances,
            extrinsic_tickets=block.extrinsic.tickets,
            pre_state_timeslot=pre_state_timeslot,
            post_state_timeslot=timeslot_output.post_state,
            post_state_validator_pool=validator_pool_output.post_state,
            pre_state_statistics=pre_state_statistics,
            header=block.header,
            reporters=self.block_context.reporters,
        )

        # GP-0.5.4-eq:12.4
        self.block_context.set_ready_work_reports()

        # GP-0.5.4-eq:12.5
        self.block_context.set_queued_work_reports(pre_state_accumulation_history)

        # GP-0.5.4-eq:12.10-12.12
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

        # Services Accumulation STF Block Data | GP-0.5.0-eq:4.18
        services_after_accumulation_output = self.components.services.state_transition_accumulation(
            accumulatable_work_reports=self.block_context.accumulatable_work_reports,
            pre_state_privileged_services=pre_state_privileged_services,
            pre_state_services=pre_state_services,
            pre_state_validator_queue=pre_state_validator_queue,
            pre_state_authorizer_queues=pre_state_authorizer_queues,
            post_state_timeslot=timeslot_output.post_state,
            post_state_entropy=entropy_output.post_state
        )

        services_after_transfers_output = self.components.services.state_transition_transfers(
            intermediate_state_after_accumulation=services_after_accumulation_output.intermediate_state_after_accumulation,
            post_state_timeslot=timeslot_output.post_state,
            deferred_transfers=services_after_accumulation_output.deferred_transfers
        )

        # Services After Preimages STF Block Data | GP-0.5.0-eq:??
        services_after_preimages_output = self.components.services.state_transition_after_preimages(
            extrinsic_preimages=block.extrinsic.preimages,
            intermediate_state_after_transfers=services_after_transfers_output.intermediate_state_after_transfers,
            post_state_timeslot=timeslot_output.post_state
        )

        # AuthorizerPools STF Block Data | GP-0.5.4-eq:4.19
        authorizer_pools_output = self.components.authorizer_pools.state_transition(
           header=block.header,
           extrinsic_guarantees=block.extrinsic.guarantees,
           post_state_authorizer_queues=services_after_accumulation_output.post_state_authorizer_queues,
           pre_state_authorizer_pools=pre_state_authorizer_pools
        )

        # RecentHistory STF Block Data | GP-0.5.0-eq:4.17
        recent_history_output = self.components.recent_history.state_transition(
           header=block.header,
           extrinsic_guarantees=block.extrinsic.guarantees,
           intermediate_state_recent_history=recent_history_intermediate_output.intermediate_state,
           beefy_commitment_map=services_after_accumulation_output.beefy_commitment_map
        )

        # Accumulation History STF | GP-0.6.1-eq:???
        accumulation_history_output = self.components.accumulation_history.state_transition(
            accumulatable_work_reports=self.block_context.accumulatable_work_reports,
            pre_state_accumulation_history=pre_state_accumulation_history,
            nr_work_results_accumulated=services_after_accumulation_output.nr_work_results_accumulated
        )

        # Accumulation Queue STF | GP-0.6.1-eq:???
        accumulation_queue_output = self.components.accumulation_queue.state_transition(
            queued_work_reports=self.block_context.queued_work_reports,
            pre_state_accumulation_queue=pre_state_accumulation_queue,
            post_state_accumulation_history=accumulation_history_output.post_state,
            pre_state_timeslot=pre_state_timeslot,
            post_state_timeslot=timeslot_output.post_state
        )

        # All state transitions successful, commit state changes
        if not dry_run:
            self.state.timeslot = timeslot_output.post_state
            self.state.entropy = entropy_output.post_state
            self.state.disputes = disputes_output.post_state
            self.state.validator_pool = validator_pool_output.post_state
            self.state.validator_archive = validator_archive_output.post_state
            self.state.safrole = safrole_output.post_state
            self.state.assurances = assurances_output.post_state
            self.state.recent_history = recent_history_output.post_state
            self.state.authorizer_pools = authorizer_pools_output.post_state
            self.state.authorizer_queues = services_after_accumulation_output.post_state_authorizer_queues
            self.state.services = services_after_preimages_output.post_state
            self.state.statistics = statistics_output.post_state
            self.state.accumulation_queue = accumulation_queue_output.post_state
            self.state.accumulation_history = accumulation_history_output.post_state
            self.state.validator_queue = services_after_accumulation_output.post_state_validator_queue
            self.state.privileged_services = services_after_accumulation_output.post_state_privileged_services

            # TODO only set local memory self.state not write to DB if not finalized
            self.components.timeslot.store_state(self.state.timeslot, transaction)
            self.components.entropy.store_state(self.state.entropy, transaction)
            self.components.disputes.store_state(self.state.disputes, transaction)
            self.components.validator_pool.store_state(self.state.validator_pool, transaction)
            self.components.validator_archive.store_state(self.state.validator_archive, transaction)
            self.components.safrole.store_state(self.state.safrole, transaction)
            self.components.assurances.store_state(self.state.assurances, transaction)
            self.components.statistics.store_state(self.state.statistics, transaction)
            self.components.services.store_state(self.state.services, transaction)
            self.components.recent_history.store_state(self.state.recent_history, transaction)
            self.components.authorizer_pools.store_state(self.state.authorizer_pools, transaction)
            self.components.authorizer_queues.store_state(self.state.authorizer_queues, transaction)
            self.components.accumulation_queue.store_state(self.state.accumulation_queue, transaction)
            self.components.accumulation_history.store_state(self.state.accumulation_history, transaction)
            self.components.validator_queue.store_state(self.state.validator_queue, transaction)
            self.components.privileged_services.store_state(self.state.privileged_services, transaction)

            # Add header to ancestor
            self.block_context.ancestor_headers.append(block.header)


        return STFOutput(
            epoch_mark=safrole_output.epoch_mark,
            tickets_mark=safrole_output.tickets_mark,
            offenders_mark=disputes_output.offenders_mark
        )

    async def _import_block(self, block: Block, dry_run=False) -> STFOutput:

        with self.state_db.transaction() as transaction:

            output = await self.state_transition(block, transaction, dry_run=dry_run)

        await self.update_state_trie()
        await self.store_block(block)
        return output

    async def store_block(self, block: Block):
        # Store block in DB
        self.block_db.put(
            b'block:' + block.header.timeslot.to_bytes(length=4, byteorder='little'), block.to_jam_bytes().to_bytes()
        )

        self.block_db.put(
            b'block_header:' + block.header.hash, block.header.to_jam_bytes().to_bytes()
        )

        self.block_db.put(
            b'block_hash:' + block.header.timeslot.to_bytes(length=4, byteorder='little'), block.header.hash
        )
        self.block_db.put(
            b'block_number:' + block.header.hash, block.header.timeslot.to_bytes(length=4, byteorder='little')
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

    def retrieve_block_hash(self, timeslot: int) -> Optional[bytes]:
        return self.block_db.get(b'block_hash:' + timeslot.to_bytes(length=4, byteorder='little'))

    def should_produce_block(self, timeslot: int, safrole_state: SafroleState) -> bool:
        slot_phase_index = timeslot % EPOCH_TIMESLOTS

        if not self.config.keys:
            # Cannot produce without validator keys
            return False

        # Check if seal-key series is fallback
        if safrole_state.slot_sealer_series.tickets is not None:
            # Retrieve current ticket
            ticket_id = safrole_state.slot_sealer_series.tickets[slot_phase_index].id
            should_produce = ticket_id in self.extrinsic.own_tickets_current

            if should_produce:
                logging.debug(f'Owning ticket ID: {ticket_id.hex()}')
            else:
                logging.debug(f'Waiting for author with ticket ID: {ticket_id.hex()}')

            return should_produce

        elif safrole_state.slot_sealer_series.keys is not None:
            author = safrole_state.slot_sealer_series.keys[slot_phase_index]

            should_produce = author == self.config.keys.bandersnatch.public_key

            if should_produce:
                logging.debug(f'Having author key: {author.hex()}')
            else:
                logging.debug(f'Waiting for author with key: {author.hex()}')

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
            logging.debug(f"VRF input: for ticket {ticket.id.hex()} with entropy {entropy_state.entropy[3].hex()}")
            return vrf_input_ticket_seal(bytes(entropy_state.entropy[3]), ticket.attempt)

        elif safrole_state.slot_sealer_series.keys is not None:
            logging.debug(f"VRF input: Fallback with entropy {entropy_state.entropy[3].hex()}")
            return vrf_input_fallback_seal(bytes(entropy_state.entropy[3]))

        else:
            raise PyjamazAppError("No valid sealing policy in current state")

    def generate_block_seal(self, header: Header, safrole_state: SafroleState, entropy_state: EntropyState) -> bytes:
        """
        GP-0.5.4-eq:6.15,6.16 (bold_H_s) | Generate block seal

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
            logging.debug(f"Ticket Seal for ticket {ticket.id.hex()} with entropy {entropy_state.entropy[3].hex()}")

            return header.generate_ticket_seal(
                bandersnatch_priv_key=self.config.keys.bandersnatch.private_key,
                entropy=bytes(entropy_state.entropy[3]),
                ticket_attempt=ticket.attempt
            )

        elif safrole_state.slot_sealer_series.keys is not None:
            logging.debug(f"Fallback Seal with entropy {entropy_state.entropy[3].hex()}")
            return header.generate_fallback_seal(
                bandersnatch_priv_key=self.config.keys.bandersnatch.private_key,
                entropy=bytes(entropy_state.entropy[3])
            )

        else:
            raise PyjamazAppError("No valid sealing policy in current state")

    def generate_entropy_source(self, timeslot: int, safrole_state: SafroleState, entropy_state: EntropyState) -> bytes:
        """
        GP-0.5.0-eq:6.17 (bold_H_v) | Generate entropy source

        Parameters
        ----------
        timeslot
        safrole_state
        entropy_state

        Returns
        -------
        bytes
        """

        seal_vrf_output = self.config.keys.bandersnatch.vrf_output(
            self.get_block_seal_vrf_input(timeslot, safrole_state, entropy_state)
        )

        return ietf_vrf_sign(
            self.config.keys.bandersnatch.private_key,
            b"jam_entropy" + seal_vrf_output,
            b""
        )

    def current_timeslot(self) -> int:
        return int(time.time() - self.config.common_era) // SLOT_PERIOD

    def slot_phase_index(self, timeslot: int) -> int:
        """
        Block Data | GP-0.5.0-eq:6.2 (m) | Function that returns the phase index into the epoch of the timeslot

        Returns
        -------
        number: int
            Phase index into the epoch of the timeslot

        """
        return timeslot % EPOCH_TIMESLOTS

    def get_next_slot_timestamp(self) -> int:
        elapsed_timeslots = (time.time() - self.config.common_era) // SLOT_PERIOD
        return self.config.common_era + (elapsed_timeslots + 1) * SLOT_PERIOD

    def get_author_index(self) -> int:
        """
        Get the author index for current node in the current validator set

        Block Data | GP-0.5.0-eq:5.9

        Parameters
        ----------

        Returns
        -------
        int
        """

        for index, validator in enumerate(self.state.safrole.validators):
            if validator.bandersnatch == self.config.keys.bandersnatch.public_key:
                return index
        raise ValueError(f"Bandersnatch {self.config.keys.bandersnatch.public_key} not found in current validator set")

    async def produce_block(self, timeslot: int, safrole_state: SafroleState, entropy_state: EntropyState) -> Block:

        if timeslot % EPOCH_TIMESLOTS > 0:
            entropy = entropy_state.entropy[2]

            if self.extrinsic.can_add_own_ticket(timeslot):

                ring_public_keys = [v.bandersnatch for v in safrole_state.validators]

                self.extrinsic.add_own_ticket(
                    ring_public_keys, entropy, self.config.keys.bandersnatch, self.get_author_index()
                )

                self.extrinsic.add_own_ticket(
                    ring_public_keys, entropy, self.config.keys.bandersnatch, self.get_author_index()
                )

                self.extrinsic.add_own_ticket(
                    ring_public_keys, entropy, self.config.keys.bandersnatch, self.get_author_index()
                )

        extrinsic = Extrinsic(
            tickets=self.extrinsic.collect_tickets(),
            disputes=ExtrinsicDisputes(verdicts=[], culprits=[], faults=[]),
            preimages=[],
            assurances=[],
            guarantees=[]
        )

        header = Header(
            parent=self.retrieve_block_hash(self.state.timeslot.number),
            parent_state_root=self.state_trie_root,
            extrinsic_hash=extrinsic.generate_extrinsic_hash(),
            timeslot=timeslot,
            # Placeholder
            epoch_marker=None,
            # Placeholder
            tickets_marker=None,
            # Placeholder
            offenders_marker=[],
            # Placeholder
            author_index=0,
            entropy_source=self.generate_entropy_source(timeslot, safrole_state, entropy_state),
            # Placeholder
            seal=bytes(96)
        )

        logging.debug(f"Produced with parent: {header.parent.hex()}")

        block = Block(
            header=header,
            extrinsic=extrinsic
        )
        with self.state_db.transaction() as transaction:

            output = await self.state_transition(block, transaction, dry_run=True)

            block.header.epoch_marker = output.epoch_mark
            block.header.tickets_marker = output.tickets_mark
            block.header.offenders_marker = output.offenders_mark
            block.header.author_index = self.get_author_index()

            block.header.seal = self.generate_block_seal(block.header, safrole_state, entropy_state)

        return block

    async def create_state_dump(self) -> StateDump:
        return StateDump(
            state_root=self.state_trie_root,
            keyvals=[(k, v, b'', b'') for k, v in self.state_db.db]
        )

    async def store_trace(self, pre_state: StateDump, block: Block, traces_dir: str):

        base_filename = f'{block.header.timeslot // EPOCH_TIMESLOTS}_{block.header.timeslot % EPOCH_TIMESLOTS:03}'

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

        logging.info(f"💾 Succesfully stored trace data {base_filename}.bin")


class StateComponents:

    def __init__(
            self,
            storage_engine: StorageEngine,
            config: AppConfig,
            block_context: BlockContext,
            app_context: AppContext
    ):

        self.timeslot = Timeslot(storage_engine, block_context, app_context)
        self.recent_history = RecentHistory(storage_engine, block_context, app_context)
        self.entropy = Entropy(storage_engine, block_context, app_context)
        self.disputes = Disputes(storage_engine, block_context, app_context)
        self.assurances = Assurances(storage_engine, block_context, app_context)
        self.validator_archive = ValidatorArchive(storage_engine, block_context, app_context)
        self.validator_pool = ValidatorPool(storage_engine, block_context, app_context)
        self.safrole = Safrole(storage_engine, block_context, app_context, config.ring_data)
        self.validator_queue = ValidatorQueue(storage_engine, block_context, app_context)
        self.statistics = Statistics(storage_engine, block_context, app_context)
        self.services = Services(storage_engine, block_context, app_context)
        self.authorizer_queues = AuthorizerQueues(storage_engine, block_context, app_context)
        self.privileged_services = PrivilegedServices(storage_engine, block_context, app_context)
        self.authorizer_pools = AuthorizerPools(storage_engine, block_context, app_context)
        self.accumulation_queue = AccumulationQueue(storage_engine, block_context, app_context)
        self.accumulation_history = AccumulationHistory(storage_engine, block_context, app_context)
