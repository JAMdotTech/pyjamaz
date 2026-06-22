import asyncio
import logging
import os
import traceback
from asyncio import TaskGroup
from typing import Dict

import anyio

from jamcodec.base import JamBytes
from pyjamaz.app import PyjamazApp
from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS
from pyjamaz.models.app import Trace
from pyjamaz.models.block import Header, Block
from pyjamaz.runtime.extrinsics import BlockExtrinsicCollector
from pyjamaz.settings import DEBUG
from pyjamaz.transport.pubsub import PubSubSignal
from pyjamaz.utils import format_hash


class AccumulatePipeline:

    def __init__(self, app: PyjamazApp, queue_size: int = 4096):
        self.app = app
        self._started = False
        self._timeslot_queue: asyncio.Queue[int] = asyncio.Queue(maxsize=queue_size)
        self._block_collect_queue: asyncio.Queue[Block] = asyncio.Queue(maxsize=queue_size)
        self._import_queue: asyncio.Queue[Block] = asyncio.Queue(maxsize=queue_size)
        self.extrinsics = BlockExtrinsicCollector(self.app.config.ring_data)
        self.collected_blocks: Dict[bytes, Block] = {}
        self.block_dir_lock = anyio.Lock()

    def start(self, task_group: TaskGroup):
        if self._started:
            return
        self._started = True
        task_group.start_soon(self._timeslot_worker)
        task_group.start_soon(self._import_worker)
        task_group.start_soon(self._block_collect_worker)
        task_group.start_soon(self._block_dir_listener)

    async def add_block(self, block: Block):
        await self._block_collect_queue.put(block)

    async def import_block(self, block: Block):
        await self._import_queue.put(block)

    async def notify_timeslot(self, timeslot: int) -> None:
        await self._timeslot_queue.put(timeslot)

    async def _block_collect_worker(self) -> None:
        while True:
            block = await self._block_collect_queue.get()

            # Check if parent exists in state storage
            async with self.app.runtime_state_lock:
                parent_exists = self.app.state_storage.get_parent(block.header) is not None

            if parent_exists:
                await self.import_block(block)

                # Try to process collected blocks
                while block.header.hash in self.collected_blocks:

                    block = self.collected_blocks.pop(block.header.hash)
                    await self.import_block(block)

            else:
                logging.info(f'🚏 Collected and queued block {format_hash(block.header.hash)} (#{block.header.timeslot})')
                self.collected_blocks[block.header.parent] = block

    async def _import_worker(self) -> None:
        while True:
            block = await self._import_queue.get()
            try:
                async with self.app.runtime_state_lock:
                    await self.app.import_block(block)
            except Exception:
                logging.exception(f"Import pipeline failed for block {format_hash(block.header.hash)}")
            finally:
                self._import_queue.task_done()


    async def _timeslot_worker(self) -> None:
        while True:
            timeslot = await self._timeslot_queue.get()
            epoch = timeslot // EPOCH_TIMESLOTS
            phase = timeslot % EPOCH_TIMESLOTS

            try:
                async with self.app.runtime_state_lock:
                    if self.app.working_state.timeslot.number >= timeslot:
                        DEBUG and logging.debug('⚠️ Timeslot did not advance; yield for 0.1 seconds')
                        await anyio.sleep(0.1)
                        continue

                    if self.app.is_epoch_change(timeslot):
                        logging.info("🗓️ Process Epoch change")

                        # TODO !! temporary to determine if first block in new epoch should be produced. Cannot be determined without
                        #  triggering state changes in STFs caused be epoch change.

                        header = Header.default()
                        header.timeslot = timeslot

                        entropy_output = self.app.components.entropy.state_transition(
                            header=header,
                            pre_state_timeslot=self.app.working_state.timeslot,
                            pre_state_entropy=self.app.working_state.entropy
                        )

                        safrole_output = self.app.components.safrole.state_transition(
                            header=header,
                            pre_state_timeslot=self.app.working_state.timeslot,
                            pre_state_safrole=self.app.working_state.safrole,
                            pre_state_validator_queue=self.app.working_state.validator_queue,
                            post_state_entropy=entropy_output.post_state,
                            post_state_disputes=self.app.working_state.disputes,
                            post_state_validator_pool=self.app.working_state.validator_pool,
                            extrinsic_tickets=[]
                        )

                        # Process tickets
                        async with self.app.block_extrinsic_lock:
                            self.app.block_extrinsic.process_epoch_change()
                            DEBUG and logging.debug(
                                f"Current tickets {[i.hex() for i in self.app.block_extrinsic.own_tickets_current]}"
                                )

                        safrole_state = safrole_output.post_state
                        entropy_state = entropy_output.post_state
                    else:
                        safrole_state = self.app.working_state.safrole
                        entropy_state = self.app.working_state.entropy

                    if self.app.should_produce_block(timeslot, safrole_state):

                        try:
                            async with self.app.block_extrinsic_lock:
                                # TODO refactor to own pipeline
                                await self.app.process_assurances()

                                parent_header_hash = self.app.retrieve_block_hash(self.app.working_state.timeslot.number)

                                if parent_header_hash is None:
                                    raise ValueError(f'No parent block found for timeslot #{self.app.working_state.timeslot.number}')

                                # Finalize parent
                                await self.app.finalize(parent_header_hash)

                                if self.app.config.replay_blocks:
                                    block = self.app.config.replay_blocks.find_next(timeslot)
                                    await self._import_queue.put(block)
                                else:

                                    block = await self.app.produce_block(timeslot, parent_header_hash, safrole_state, entropy_state)

                                    if self.app.pubsub:
                                        await self.app.pubsub.publish(PubSubSignal(topic=MESSAGE_TYPES.PRODUCED_BLOCK, data=block))

                                    logging.info(
                                        f'🎁 Produced block for #{block.header.timeslot} | hash {format_hash(block.header.hash)} | parent {format_hash(block.header.parent)} | epoch #{epoch} | phase #{phase}'
                                        )
                        except Exception as e:
                            logging.info(f'🗑️ Discarded produced block for #{timeslot}: {e}')
                            DEBUG and logging.debug(traceback.format_exc())
                            # Rollback state from DB
                            self.app.working_state = self.app.retrieve_jam_state()
                            # TODO Make transactional
                            async with self.app.block_extrinsic_lock:
                                self.app.block_extrinsic.clear_tickets()

                    else:
                        logging.info(f'💤 Waiting for block #{timeslot} | epoch #{epoch} | phase #{phase}')
            except Exception:
                logging.exception("Work pipeline failed for timeslot %s", timeslot)
            finally:
                self._timeslot_queue.task_done()

    async def _block_dir_listener(self):
        """
        TODO TEMP block dir listener

        Returns
        -------

        """

        seen_files = set()

        while True:
            # Run the directory check in a separate thread (non-blocking)
            new_files = await anyio.to_thread.run_sync(
                lambda: {f for f in os.listdir(self.app.config.import_block_path) if f.endswith('.bin')} - seen_files
            )

            if new_files:
                for filename in sorted(new_files):
                    filepath = os.path.join(self.app.config.import_block_path, filename)

                    try:
                        async with self.block_dir_lock:

                            with open(filepath, 'rb') as file:
                                trace = Trace.from_jam_bytes(JamBytes(file.read()))
                                await self.add_block(trace.block)

                    except Exception as e:
                        logging.error(f"Failed to process {filepath}: {e}")

                # Update the seen_files set to include the newly processed files
                seen_files.update(new_files)

            await anyio.sleep(.5)
