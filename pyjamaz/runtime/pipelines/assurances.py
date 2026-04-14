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


class AssurancesPipeline:

    def __init__(self, app: PyjamazApp, queue_size: int = 4096):
        self.app = app
        self._started = False
        self._block_hash_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=queue_size)

    def start(self, task_group: TaskGroup):
        if self._started:
            return
        self._started = True
        task_group.start_soon(self._assurances_worker)


    async def _assurances_worker(self) -> None:
        while True:
            block_hash = await self._block_hash_queue.get()
            logging.info('Check D3L availability for work packages in block %s ', format_hash(block_hash))
