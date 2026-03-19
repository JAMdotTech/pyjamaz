import logging
import time
from asyncio import TaskGroup

import anyio

from pyjamaz.app import PyjamazApp
from pyjamaz.models.block import TicketEnvelope, Assurance, Guarantee, Preimage
from pyjamaz.runtime.refine import RefinePipeline
from pyjamaz.runtime.accumulate import AccumulatePipeline
from pyjamaz.settings import DEBUG


class NodeRuntime:
    def __init__(self, app: PyjamazApp):
        self.app = app
        self._started = False
        self.refine_pipeline = RefinePipeline(app)
        self.accumulate_pipeline = AccumulatePipeline(app)

    def start(self, task_group: TaskGroup):
        if self._started:
            return
        self._started = True

        self.refine_pipeline.start(task_group)
        self.accumulate_pipeline.start(task_group)
        task_group.start_soon(self._timeslot_worker)

    async def _timeslot_worker(self) -> None:
        while True:
            timeslot = self.app.current_timeslot()
            await self.refine_pipeline.notify_timeslot(timeslot=timeslot)
            await self.accumulate_pipeline.notify_timeslot(timeslot=timeslot)
            DEBUG and logging.debug(f"⏳️ Timeslot worker: {timeslot}")
            await anyio.sleep(max(0.01, self.app.get_next_slot_timestamp() - time.time() + 0.01))

    async def notify_timeslot(self, timeslot: int):
        await self.refine_pipeline.notify_timeslot(timeslot)

    def ingest_ticket(self, ticket: TicketEnvelope) -> None:
        self.accumulate_pipeline.ingest_ticket(ticket)

    def ingest_assurance(self, assurance: Assurance) -> None:
        self.accumulate_pipeline.ingest_assurance(assurance)

    def ingest_guarantee(self, guarantee: Guarantee) -> None:
        self.accumulate_pipeline.ingest_guarantee(guarantee)

    def ingest_preimage(self, preimage: Preimage) -> None:
        self.accumulate_pipeline.ingest_preimage(preimage)

