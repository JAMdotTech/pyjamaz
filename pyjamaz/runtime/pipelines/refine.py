import asyncio
import logging
from asyncio import TaskGroup
from typing import Dict, List

import anyio

from pyjamaz.app import PyjamazApp
from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.runtime.extrinsics import WorkpackageExtrinsicCollector
from pyjamaz.models.block import Credential, Guarantee
from pyjamaz.models.common import WorkPackage, WorkPackageStatus, WorkPackageReportableStatus, \
    WorkPackageReportedStatus, BlockDesc
from pyjamaz.runtime.types import WorkPackageQueueItem
from pyjamaz.settings import DEBUG, GUARANTEE_SIGNATURE_WAIT_PERIOD
from pyjamaz.transport.pubsub import PubSubSignal
from pyjamaz.utils import format_hash


class RefinePipeline:

    def __init__(self, app: PyjamazApp, queue_size: int = 4096):
        self.app = app
        self._pending_work_packages: Dict[bytes, WorkPackageQueueItem] = {}
        self._work_package_extrinsics = WorkpackageExtrinsicCollector()
        self._refine_queue: asyncio.Queue[WorkPackageQueueItem] = asyncio.Queue(maxsize=queue_size)
        self._guarantee_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=queue_size)
        self._assurances_queue: asyncio.Queue[WorkPackageQueueItem] = asyncio.Queue(maxsize=queue_size)
        self._timeslot_queue: asyncio.Queue[int] = asyncio.Queue(maxsize=queue_size)
        self._started = False

    def start(self, task_group: TaskGroup):
        if self._started:
            return
        self._started = True

        task_group.start_soon(self._refine_worker)
        # task_group.start_soon(self._refine_worker)
        task_group.start_soon(self._timeslot_worker)
        task_group.start_soon(self._guarantuee_worker)

    def add_work_package(self, work_package: WorkPackage, extrinsics: List[bytes]):

        self._pending_work_packages[work_package.hash()] = WorkPackageQueueItem(
            work_package=work_package, status=WorkPackageStatus(
                Reportable=WorkPackageReportableStatus(
                    remaining_blocks=4
                    )
                )
            )

        self._work_package_extrinsics.add(work_package, extrinsics)

        logging.info(f"📥 Added work package to queue: {format_hash(work_package.hash())}")

    async def add_signature(self, work_package_hash, signature: Credential):
        DEBUG and logging.debug(f'Adding signature for  {format_hash(work_package_hash)}')
        self._pending_work_packages[work_package_hash].signatures.append(signature)
        await self._guarantee_queue.put(work_package_hash)

    async def notify_timeslot(self, timeslot: int) -> None:
        await self._timeslot_queue.put(timeslot)

    async def _timeslot_worker(self) -> None:
        while True:
            timeslot = await self._timeslot_queue.get()
            try:
                logging.info(f'👨‍💻 Processing Refine | slot={timeslot} | core={self.app.get_core_assigment()}')

                # wp_queue_item = None
                # cleanup_queue = []
                #
                # # Clean up expired work-packages
                # for h, w in self._pending_work_packages.items():
                #     if not self.app.working_state.recent_history.get_recent_block(w.work_package.context.lookup_anchor):
                #         cleanup_queue.append(h)
                #
                # for h in cleanup_queue:
                #     del self._pending_work_packages[h]
                #     logging.info(f"🗑️ Discarded outdated work package {format_hash(h)}")

                if self.app.get_core_assigment() is None:
                    continue

                # Find first authorized work package
                for h, w in self._pending_work_packages.items():
                    if w.status.enum_value()[0] == 'Reportable':
                        if self.app.working_state.authorizer_pools.is_authorized(
                                w.work_package, self.app.get_core_assigment()
                        ):
                            self._pending_work_packages[h].status = WorkPackageStatus(Reporting=True)
                            await self._refine_queue.put(self._pending_work_packages[h])
                            logging.info(f'Added work package {format_hash(w.work_package.hash())} to worker queue')

            except Exception:
                logging.exception("Work pipeline failed for timeslot %s", timeslot)
            finally:
                self._timeslot_queue.task_done()

    async def _refine_worker(self) -> None:
        while True:
            wp_item = await self._refine_queue.get()

            logging.info(f'👨‍💻 Processing work-package {format_hash(wp_item.work_package.hash())} [{wp_item.status.enum_value()[0]}]')

            # if self.get_core_assigment() is None:
            #     raise ProcessWorkpackageError("Cannot process work package: no core assignment")

            work_package = wp_item.work_package

            # Prepare extrinsic data (GP-0.7.2-eq:B.6 bold_x_flat)
            extrinsics = [
                [self._work_package_extrinsics.get(work_package, x.hash, x.len) for x in w.extrinsic]
                for w in work_package.items
            ]

            # Set code
            work_package.set_authorization_code(self.app.working_state.services)

            # Todo move work_result_computation to here
            work_report = await anyio.to_thread.run_sync(
                self.app.work_result_computation,
                work_package,
                self.app.get_core_assigment(),
                self.app.working_state.services,
                extrinsics,
            )

            logging.info(f'👨‍💻Created work-report {format_hash(work_report.hash())}')

            wp_item.work_report = work_report

            # Update work package status
            wp_item.status = WorkPackageStatus(
                Reported=WorkPackageReportedStatus(
                    reported_in=BlockDesc(
                        slot=self.app.working_state.timeslot.number,
                        header_hash=self.app.retrieve_block_hash(self.app.working_state.timeslot.number)
                    ),
                    core=self.app.get_core_assigment(),
                    report_hash=work_report.hash()
                )
            )

            if self.app.pubsub:
                # Send signal
                await self.app.pubsub.publish(
                    PubSubSignal(
                        topic=MESSAGE_TYPES.WORK_PACKAGE_STATUS,
                        data=[wp_item.status.to_json()]
                    )
                )

            # Clean up work package extrinsics
            self._work_package_extrinsics.clear(work_package)

            # Guarantee signature
            credential = await self.app.create_guarantee_signature(work_report)

            await self.add_signature(work_package.hash(), credential)


            #TODO
            # TODO exchange signature with other core members
            for v_idx, assignment in enumerate(self.app.block_context.guarantor_assignments):
                if assignment.validator_ed25519 != self.app.config.keys.ed25519.public_key and assignment.core_index == self.app.get_core_assigment():
                    signature = await self.app.create_guarantee_signature_for_validator(work_report, v_idx)
                    # await asyncio.sleep(3)
                    await self.add_signature(work_package.hash(), signature)

            # await self.app.guarantee_work_report(work_report, self.app.current_timeslot())

            DEBUG and logging.debug(f"Processed work package: {format_hash(work_package.hash())}")



    async def _guarantuee_worker(self) -> None:
        while True:
            wp_hash = await self._guarantee_queue.get()
            wp_item = self._pending_work_packages[wp_hash]

            DEBUG and logging.debug(f'Checking signature for guarantee {format_hash(wp_hash)}')
            if wp_item.work_report and len(wp_item.signatures) >= 2:
                DEBUG and logging.debug(f'Work-report {format_hash(wp_item.work_report.hash())} has {len(wp_item.signatures)} signatures')

                if len(wp_item.signatures) == 2:
                    # Enter grace period to wait for final core member to complete work
                    await asyncio.sleep(GUARANTEE_SIGNATURE_WAIT_PERIOD)
                    DEBUG and logging.debug(f'Waiting for third')

                # Ingest guarantee extrinsic
                guarantee = Guarantee(
                    report=wp_item.work_report,
                    slot=self.app.current_timeslot(),
                    signatures=wp_item.signatures
                )

                DEBUG and logging.debug(f'Ingested guarantee extrinsic with {len(wp_item.signatures)} signatures')
                # TODO move to accumulate pipeline?
                self.app.block_extrinsic.add_guarantee(guarantee)

    async def _assurances_worker(self) -> None:
        while True:
            wp_item = await self._assurances_queue.get()

            DEBUG and logging.debug(f'Checking D3L for wp={format_hash(wp_item.work_report.hash())}')

            # TODO implement
