import asyncio
import logging
import traceback
from asyncio import TaskGroup

import anyio

from pyjamaz.app import PyjamazApp
from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS
from pyjamaz.models.block import Header
from pyjamaz.runtime.extrinsics import BlockExtrinsicCollector
from pyjamaz.settings import DEBUG
from pyjamaz.transport.pubsub import PubSubSignal
from pyjamaz.utils import format_hash


class AccumulatePipeline:

    def __init__(self, app: PyjamazApp, queue_size: int = 4096):
        self.app = app
        self._started = False
        self._timeslot_queue: asyncio.Queue[int] = asyncio.Queue(maxsize=queue_size)
        self.extrinsics = BlockExtrinsicCollector(self.app.config.ring_data)

    def start(self, task_group: TaskGroup):
        if self._started:
            return
        self._started = True
        task_group.start_soon(self._timeslot_worker)

    async def notify_timeslot(self, timeslot: int) -> None:
        await self._timeslot_queue.put(timeslot)

    async def _timeslot_worker(self) -> None:
        while True:
            timeslot = await self._timeslot_queue.get()
            epoch = timeslot // EPOCH_TIMESLOTS
            phase = timeslot % EPOCH_TIMESLOTS

            try:
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
                        # TODO refactor to own pipeline
                        await self.app.process_assurances()

                        parent_header_hash = self.app.retrieve_block_hash(self.app.working_state.timeslot.number)

                        if parent_header_hash is None:
                            raise ValueError(f'No parent block found for timeslot #{self.app.working_state.timeslot.number}')

                        # Finalize parent
                        await self.app.finalize(parent_header_hash)

                        if self.app.config.replay_blocks:
                            block = self.app.config.replay_blocks.find_next(timeslot)
                            if block:
                                await self.app.import_block(block)
                        else:
                            extrinsics = self.extrinsics


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
                        self.app.block_extrinsic.clear_tickets()

                else:
                    logging.info(f'💤 Waiting for block #{timeslot} | epoch #{epoch} | phase #{phase}')
            except Exception:
                logging.exception("Work pipeline failed for timeslot %s", timeslot)
            finally:
                self._timeslot_queue.task_done()
