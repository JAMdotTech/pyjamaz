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

from pyjamaz.exceptions import BlockValidationError, PyjamazAppError, BlockValidationErrorCode
from pyjamaz.extrinsic import ExtrinsicAccumulator
from pyjamaz.graypaper_constants import MAXIMUM_AUTHORIZATION_QUEUE_ITEMS, CORE_COUNT, EPOCH_TIMESLOTS, \
    SLOT_PERIOD
from pyjamaz.merkle import PatriciaMerkleTrie
from pyjamaz.models.trace import StateDump, Trace
from pyjamaz.signing import Ed25519Keypair, BandersnatchKeypair
from pyjamaz.state.base import AppContext
from pyjamaz.storage import StorageEngine, Transaction

from pyjamaz.state.components import Timeslot, Entropy, Safrole, ValidatorArchive, ValidatorPool, ValidatorQueue, \
    RecentHistory, Disputes, Assurances, Statistics, PrivilegedServices, AuthorizerQueues, AuthorizerPools, Services
from pyjamaz.models.block import Block, Header, Extrinsic, ExtrinsicDisputes, TicketEnvelope, BlockContext
from pyjamaz.models.state import JamState, ServicesState, AuthorizerQueuesState, \
    BeefyCommitmentMap, AccumulationQueueState, AccumulationHistoryState
from pyjamaz.models.stf_output import STFOutput, SafroleErrorCode
from pyjamaz.utils import vrf_input_fallback_seal, vrf_input_ticket_seal

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

        # self.storage_engine: StorageInterface = config.storage_engine

        self.state_db: StorageEngine = config.storage_engine.namespace(b"state")
        self.block_db: StorageEngine = config.storage_engine.namespace(b"block")
        self.app_db: StorageEngine = config.storage_engine.namespace(b"app")
        self.network_bootstrap:bool = False
        self.import_queue:List[Block] = []

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

        self.latest_epoch = None

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
                #logging.debug(f" TEMP BREAK block from process_import_queue: {block.header.timeslot}")
                continue

            await self.import_block(block)
            logging.info(f'✅ Block {block.header.timeslot} succesfully imported from process_import_queue.')


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
            authorizer_queues=AuthorizerQueuesState(
                authorizer_queues=[
                    [bytes(32) for _ in range(MAXIMUM_AUTHORIZATION_QUEUE_ITEMS)] for _ in range(CORE_COUNT)
                ]
            ),
            privileged_services=self.components.privileged_services.retrieve_state(),
            disputes=self.components.disputes.retrieve_state(),
            statistics=self.components.statistics.retrieve_state(),
            accumulation_queue=AccumulationQueueState(
                accumulation_queue=[
                    [] for _ in range(EPOCH_TIMESLOTS)
                ]
            ),
            accumulation_history=AccumulationHistoryState(
                accumulation_history=[bytes(32) for _ in range(EPOCH_TIMESLOTS)]
            )
            # TODO retrieve accumulation_queue and accumulation_history from DB
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
        # TODO store accumulation_queue and accumulation_history


    async def update_state_trie(self):
        """
        Updated the Patricia state trie.

        TODO create separate DB and only update affected branches for performance; now the whole state have to be
          in memory
        """
        state_trie = PatriciaMerkleTrie(list(self.state_db))
        self.state_trie_root = state_trie.root()

    async def process_timeslot(self, timeslot: int):
        if self.is_epoch_change(timeslot):

            self.latest_epoch = timeslot // EPOCH_TIMESLOTS
            logging.info("🗓️ Process Epoch change")

            # TODO !! temporary to determine if first block in new epoch should be produced. Cannot be determined without
            #  triggering state changes in STFs caused be epoch change.

            header = Header.default()
            header.timeslot = timeslot

            entropy_output = self.components.entropy.state_transition(
                header=header,
                pre_state_timeslot=self.state.timeslot,
                pre_state_entropy=self.state.entropy
            )

            post_safrole_state = self.components.safrole.state_transition(
                header=header,
                pre_state_timeslot=self.state.timeslot,
                pre_state_safrole=self.state.safrole,
                pre_state_validator_queue=self.state.validator_queue,
                post_state_entropy=entropy_output.post_state,
                post_state_disputes=self.state.disputes,
                post_state_validator_pool=self.state.validator_pool,
                extrinsic_tickets=[]
            )
            # Update slot_sealer_series in advance
            self.state.safrole.slot_sealer_series = post_safrole_state.post_state.slot_sealer_series
            logging.debug(f'New slot_sealer_series: {self.state.safrole.slot_sealer_series.to_json()}')
            # Process tickets
            self.extrinsic.process_epoch_change()
            logging.debug(f"Current tickets {[i.hex() for i in self.extrinsic.own_tickets_current]}")

    def validate_header(self, header: Header):

        if 0 < header.timeslot <= self.state.timeslot.number or header.timeslot > self.current_timeslot():
            raise BlockValidationError(SafroleErrorCode.bad_slot)

        parent_hash = self.retrieve_block_hash(self.state.timeslot.number) or bytes(32)

        if header.parent != parent_hash:
            raise BlockValidationError(
                f"Parent hash {header.parent.hex()} does not match latest block in state 0x{parent_hash.hex()}"
            )

        if header.parent_state_root != self.state_trie_root:
            raise BlockValidationError(
                f"Parent state root {header.parent_state_root.hex()} does not match with  0x{self.state_trie_root.hex()}"
            )


        # Validate seal
        author_key = self.get_author_bandersnatch_key(header.author_index)

        if self.state.safrole.slot_sealer_series.tickets is not None:
            ticket = self.state.safrole.slot_sealer_series.tickets[header.timeslot % EPOCH_TIMESLOTS]
            logging.debug(
                f'Validate ticket | Timeslot: {header.timeslot} | Ticket ID: {ticket.id.hex()} | Author: {author_key.hex()} | Entropy: {self.state.entropy.entropy[3].hex()} '
            )
            header.verify_ticket_seal(author_key, ticket, self.state.entropy.entropy[3])

        elif self.state.safrole.slot_sealer_series.keys is not None:
            # Fallback method
            sealer_key = self.state.safrole.slot_sealer_series.keys[header.timeslot % EPOCH_TIMESLOTS]

            logging.debug(
                f'Validate key | Timeslot: {header.timeslot} |  Author: {sealer_key.hex()} | Entropy: {self.state.entropy.entropy[3].hex()}'
                )

            if author_key != sealer_key:
                raise BlockValidationError("Invalid author key")
            try:

                logging.debug(f"Validate Seal with entropy {self.state.entropy.entropy[3].hex()}")
                header.verify_fallback_seal(sealer_key, self.state.entropy.entropy[3])

            except ValueError:
                raise BlockValidationError("Invalid seal key")

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

        if self.state.timeslot.number == 0 and slotnumber % EPOCH_TIMESLOTS != 0:
            return False

        return self.latest_epoch != slotnumber // EPOCH_TIMESLOTS

    def validate_block(self, block: Block):

        # Check extrinsic hash
        if block.header.extrinsic_hash != block.extrinsic.generate_extrinsic_hash():
            raise BlockValidationError(BlockValidationErrorCode.extrinsic_hash_mismatch)

        self.validate_header(block.header)

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
        self.block_context.initialize()

        # Update app context
        self.app_context.transaction = transaction

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

        pre_state_services = self.state.services
        pre_state_authorizer_queues = self.state.authorizer_queues
        pre_state_privileged_services = self.state.privileged_services
        pre_state_authorizer_pools = self.state.authorizer_pools
        pre_state_accumulation_history = self.state.accumulation_history
        pre_state_accumulation_queue = self.state.accumulation_queue

        # Validate quality of dispute extrinsic data
        self.components.disputes.validate_extrinsic_disputes(
            disputes=block.extrinsic.disputes,
            current_epoch=pre_state_timeslot.epoch_number(),
            current_validators=pre_state_validator_pool.validators,
            prev_validators=pre_state_validator_archive.validators
        )

        # Validate quality of preimage extrinsic data
        self.components.services.validate_extrinsic_preimages(
            extrinsic_preimages=block.extrinsic.preimages,
            pre_state_services=pre_state_services
        )

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

        # Validator Pool STF Block Data | GP-0.5.0-eq:4.10
        validator_pool_output = self.components.validator_pool.state_transition(
            header=block.header,
            pre_state_timeslot=pre_state_timeslot,
            pre_state_validator_pool=pre_state_validator_pool,
            pre_state_safrole=pre_state_safrole
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
           header=block.header
        )

        # Assurances After Assurances STF Block Data | GP-0.5.0-eq:4.14
        assurances_after_assurances_output = self.components.assurances.state_transition_after_assurances(
            extrinsic_assurances=block.extrinsic.assurances,
            intermediate_state_assurances_after_disputes=assurances_after_disputes_output.intermediate_state_after_disputes,
        )

        # Services After Preimages STF Block Data | GP-0.5.0-eq:??
        services_after_preimages_output = self.components.services.state_transition_after_preimages(
           extrinsic_preimages=block.extrinsic.preimages,
           pre_state_services=pre_state_services,
           post_state_timeslot=timeslot_output.post_state
        )

        self.block_context.set_guarantor_assignments(
            post_entropy=entropy_output.post_state,
            post_timeslot=timeslot_output.post_state,
            post_validator_pool=validator_pool_output.post_state,
        )
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

        # Services Accumulation STF Block Data | GP-0.5.0-eq:4.18
        #services_output = services.state_transition(
        #    extrinsic_assurances=block.extrinsic.assurances,
        #    post_state_assurances=assurances_output.post_state,
        #    intermediate_state_services_after_preimages=services_after_preimages_output.intermediate_state_after_preimages,
        #    pre_state_privileged_services=pre_state_privileged_services,
        #    pre_state_validator_queue=pre_state_validator_queue,
        #    pre_state_authorizer_queues=pre_state_authorizer_queues
        #)

        # AuthorizerPools STF Block Data | GP-0.5.4-eq:4.19
        authorizer_pools_output = self.components.authorizer_pools.state_transition(
           header=block.header,
           extrinsic_guarantees=block.extrinsic.guarantees,
           # Todo: posterior state of authorizer_queues determined by service accumulation (privileged_services)
           # post_state_authorizer_queues=authorizer_queues_output.post_state,
           post_state_authorizer_queues=pre_state_authorizer_queues,
           pre_state_authorizer_pools=pre_state_authorizer_pools
        )

        # RecentHistory STF Block Data | GP-0.5.0-eq:4.17
        recent_history_output = self.components.recent_history.state_transition(
           header=block.header,
           extrinsic_guarantees=block.extrinsic.guarantees,
           intermediate_state_recent_history=recent_history_intermediate_output.intermediate_state,
           # Todo: BeefyCommitmentMap is determined by service accumulation (part of STF secondary output)
           beefy_commitment_map=BeefyCommitmentMap(beefy_commitment_map={})
           #beefy_commitment_map=services_output.beefy_commitment_map
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
            self.state.statistics = statistics_output.post_state
            self.state.authorizer_pools = authorizer_pools_output.post_state

            # TODO only set local memory self.state not write to DB if not finalized
            self.components.timeslot.store_state(timeslot_output.post_state, transaction)
            self.components.entropy.store_state(entropy_output.post_state, transaction)
            self.components.disputes.store_state(disputes_output.post_state, transaction)
            self.components.validator_pool.store_state(validator_pool_output.post_state, transaction)
            self.components.validator_archive.store_state(validator_archive_output.post_state, transaction)
            self.components.safrole.store_state(safrole_output.post_state, transaction)
            self.components.assurances.store_state(assurances_output.post_state, transaction)
            self.components.statistics.store_state(statistics_output.post_state, transaction)
            # Todo: add remaining state components: services
            # Todo: research but likely also add posterior state of privileged services output (validator_queue, authorization_queues, privileged_services)
            # TODO TBD add when clear how to determine block hash, work_report_hashes and accumulate_root (deprecated by previous todo)
            self.components.recent_history.store_state(recent_history_output.post_state, transaction)
            self.components.authorizer_pools.store_state(authorizer_pools_output.post_state, transaction)

        return STFOutput(
            epoch_mark=safrole_output.epoch_mark,
            tickets_mark=safrole_output.tickets_mark,
            offenders_mark=disputes_output.offenders_mark
        )

    async def _import_block(self, block: Block, validate=True) -> STFOutput:
        try:
            with self.state_db.transaction() as transaction:

                if validate:
                    self.validate_block(block)

                output = await self.state_transition(block, transaction)

            await self.update_state_trie()
            await self.store_block(block)
            self.latest_epoch = block.header.timeslot // EPOCH_TIMESLOTS
            return output

        except Exception as e:
            # Rollback state
            logging.debug(f'Import failed {e}; Rollback state')
            self.state = self.retrieve_jam_state()
            raise e

    async def store_block(self, block: Block):
        # Store block in DB
        self.block_db.put(
            b'block:' + block.header.timeslot.to_bytes(length=4, byteorder='little'), block.to_jam_bytes().to_bytes()
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

    def retrieve_block_hash(self, timeslot: int) -> Optional[bytes]:
        return self.block_db.get(b'block_hash:' + timeslot.to_bytes(length=4, byteorder='little'))

    def should_produce_block(self) -> bool:
        slot_phase_index = self.current_slot_phase_index()

        if not self.config.keys:
            # Cannot produce without validator keys
            return False

        # Check if seal-key series is fallback
        if self.state.safrole.slot_sealer_series.tickets is not None:
            # Retrieve current ticket
            ticket_id = self.state.safrole.slot_sealer_series.tickets[slot_phase_index].id
            should_produce = ticket_id in self.extrinsic.own_tickets_current

            if should_produce:
                logging.debug(f'Owning ticket ID: {ticket_id.hex()}')
            else:
                logging.debug(f'Waiting for author with ticket ID: {ticket_id.hex()}')

            return should_produce

        elif self.state.safrole.slot_sealer_series.keys is not None:
            author = self.state.safrole.slot_sealer_series.keys[slot_phase_index]

            should_produce = author == self.config.keys.bandersnatch.public_key

            if should_produce:
                logging.debug(f'Having author key: {author.hex()}')
            else:
                logging.debug(f'Waiting for author with key: {author.hex()}')

            return should_produce

    def get_block_seal_vrf_input(self) -> bytes:
        """
        Get relevant seal VRF input (ticket or fallback)

        Returns
        -------
        bytes
        """
        if self.state.safrole.slot_sealer_series.tickets is not None:

            ticket = self.state.safrole.slot_sealer_series.tickets[self.current_slot_phase_index()]
            logging.debug(f"VRF input: for ticket {ticket.id.hex()} with entropy {self.state.entropy.entropy[3].hex()}")
            return vrf_input_ticket_seal(bytes(self.state.entropy.entropy[3]), ticket.attempt)

        elif self.state.safrole.slot_sealer_series.keys is not None:
            logging.debug(f"VRF input: Fallback with entropy {self.state.entropy.entropy[3].hex()}")
            return vrf_input_fallback_seal(bytes(self.state.entropy.entropy[3]))

        else:
            raise PyjamazAppError("No valid sealing policy in current state")

    def generate_block_seal(self, header: Header) -> bytes:
        """
        GP-0.5.4-eq:6.15,6.16 (bold_H_s) | Generate block seal

        Parameters
        ----------
        header

        Returns
        -------
        bytes
        """

        if self.state.safrole.slot_sealer_series.tickets is not None:

            ticket = self.state.safrole.slot_sealer_series.tickets[self.current_slot_phase_index()]
            logging.debug(f"Ticket Seal for ticket {ticket.id.hex()} with entropy {self.state.entropy.entropy[3].hex()}")

            return header.generate_ticket_seal(
                bandersnatch_priv_key=self.config.keys.bandersnatch.private_key,
                entropy=bytes(self.state.entropy.entropy[3]),
                ticket_attempt=ticket.attempt
            )

        elif self.state.safrole.slot_sealer_series.keys is not None:
            logging.debug(f"Fallback Seal with entropy {self.state.entropy.entropy[3].hex()}")
            return header.generate_fallback_seal(
                bandersnatch_priv_key=self.config.keys.bandersnatch.private_key,
                entropy=bytes(self.state.entropy.entropy[3])
            )

        else:
            raise PyjamazAppError("No valid sealing policy in current state")

    def generate_entropy_source(self) -> bytes:
        """
        # Block Data | GP-0.5.0-eq:6.17 (bold_H_v)

        Returns
        -------
        bytes
        """

        seal_vrf_output = self.config.keys.bandersnatch.vrf_output(self.get_block_seal_vrf_input())

        return ietf_vrf_sign(
            self.config.keys.bandersnatch.private_key,
            b"jam_entropy" + seal_vrf_output,
            b""
        )

    def current_timeslot(self) -> int:
        return int(time.time() - self.config.common_era) // SLOT_PERIOD

    def current_epoch(self) -> int:
        return self.current_timeslot() // EPOCH_TIMESLOTS

    def current_slot_phase_index(self) -> int:
        """
        Block Data | GP-0.5.0-eq:6.2 (m) | Function that returns the phase index into the epoch of the timeslot

        Returns
        -------
        number: int
            Phase index into the epoch of the timeslot

        """
        return self.current_timeslot() % EPOCH_TIMESLOTS

    def get_next_slot_timestamp(self) -> int:
        elapsed_timeslots = (time.time() - self.config.common_era) // SLOT_PERIOD
        return self.config.common_era + (elapsed_timeslots + 1) * SLOT_PERIOD

    def get_author_bandersnatch_key(self, author_index: int) -> bytes:
        """
        Get the bandersnatch key for the author with corresponding index from the current validator set

        Block Data | GP-0.5.0-eq:5.9

        Parameters
        ----------
        author_index

        Returns
        -------
        bytes
        """
        return self.state.safrole.validators[author_index].bandersnatch

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

    async def produce_block(self, timeslot: int) -> Block:

        if timeslot % EPOCH_TIMESLOTS > 0:
            entropy = self.state.entropy.entropy[2]

            if self.extrinsic.can_add_own_ticket(timeslot):

                ring_public_keys = [v.bandersnatch for v in self.state.safrole.validators]

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
            parent=self.retrieve_block_hash(self.state.timeslot.number) or bytes(32),
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
            entropy_source=self.generate_entropy_source(),
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

            block.header.seal = self.generate_block_seal(block.header)

        return block

    async def seal_block(self, block: Block):
        pass

    async def create_state_dump(self) -> StateDump:
        return StateDump(
            state_root=self.state_trie_root,
            keyvals=[(k, v) for k, v in self.state_db.db]
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

        logging.debug(f"Succesfully stored trace data for #{block.header.timeslot}")


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
