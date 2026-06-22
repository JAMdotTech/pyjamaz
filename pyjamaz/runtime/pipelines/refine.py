import asyncio
import logging
from asyncio import TaskGroup
from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, List

import anyio

from pyjamaz import settings
from pyjamaz.app import Keys, PyjamazApp
from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.runtime.extrinsics import WorkpackageExtrinsicCollector
from pyjamaz.models.block import Credential, Guarantee
from pyjamaz.models.common import WorkPackage, WorkPackageStatus, WorkPackageReportableStatus, \
    WorkPackageReportedStatus, BlockDesc, WorkReport
from pyjamaz.runtime.types import WorkPackageQueueItem
from pyjamaz.settings import DEBUG, GUARANTEE_SIGNATURE_WAIT_PERIOD
from pyjamaz.transport.pubsub import PubSubSignal
from pyjamaz.utils import format_hash


@dataclass
class RefineQueueEntry:
    core_index: int
    item: WorkPackageQueueItem


@dataclass
class PostReportQueueEntry:
    work_package_hash: bytes
    work_report: WorkReport
    own_validator_index: int
    other_validator_indices: list[int]


class RefinePipeline:

    def __init__(self, app: PyjamazApp, queue_size: int = 4096):
        self.app = app
        self._pending_work_packages: Dict[bytes, WorkPackageQueueItem] = {}
        self._work_package_extrinsics = WorkpackageExtrinsicCollector()
        self._refine_queue: asyncio.Queue[RefineQueueEntry] = asyncio.Queue(maxsize=queue_size)
        self._post_report_queue: asyncio.Queue[PostReportQueueEntry] = asyncio.Queue(maxsize=queue_size)
        self._guarantee_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=queue_size)
        self._assurances_queue: asyncio.Queue[WorkPackageQueueItem] = asyncio.Queue(maxsize=queue_size)
        self._timeslot_queue: asyncio.Queue[int] = asyncio.Queue(maxsize=queue_size)
        self._schedule_event = asyncio.Event()
        self._schedule_lock = asyncio.Lock()
        self._active_cores: set[int] = set()
        self._guaranteed_work_packages: set[bytes] = set()
        self._started = False

    def start(self, task_group: TaskGroup):
        if self._started:
            return
        self._started = True

        for _ in range(max(1, settings.WORKPACKAGE_REFINE_WORKERS)):
            task_group.start_soon(self._refine_worker)
        task_group.start_soon(self._scheduler_worker)
        task_group.start_soon(self._timeslot_worker)
        task_group.start_soon(self._post_report_worker)
        task_group.start_soon(self._guarantuee_worker)

    def add_work_package(self, work_package: WorkPackage, extrinsics: List[bytes]):
        work_package_hash = work_package.hash()

        self._pending_work_packages[work_package_hash] = WorkPackageQueueItem(
            work_package=work_package, status=WorkPackageStatus(
                Reportable=WorkPackageReportableStatus(
                    remaining_blocks=4
                    )
                )
            )

        self._work_package_extrinsics.add(work_package, extrinsics)

        logging.info(f"📥 Added work package to queue: {format_hash(work_package_hash)}")
        logging.info(f"cycle_event=work_package_received work_package={work_package_hash.hex()}")
        self._trigger_schedule("work_package_received")

    async def add_signature(self, work_package_hash, signature: Credential):
        DEBUG and logging.debug(f'Adding signature for  {format_hash(work_package_hash)}')
        self._pending_work_packages[work_package_hash].signatures.append(signature)
        await self._guarantee_queue.put(work_package_hash)

    async def notify_timeslot(self, timeslot: int) -> None:
        await self._timeslot_queue.put(timeslot)

    def _trigger_schedule(self, reason: str) -> None:
        DEBUG and logging.debug(f"Trigger refine scheduling: {reason}")
        self._schedule_event.set()

    async def _release_core(self, core_index: int) -> None:
        async with self._schedule_lock:
            self._active_cores.discard(core_index)
        self._trigger_schedule("core_released")

    async def _timeslot_worker(self) -> None:
        while True:
            timeslot = await self._timeslot_queue.get()
            try:
                async with self.app.runtime_state_lock:
                    core_assignment = self.app.get_core_assigment()

                logging.info(f'👨‍💻 Processing Refine | slot={timeslot} | core={core_assignment}')
                self._trigger_schedule("timeslot")
            except Exception:
                logging.exception("Work pipeline failed for timeslot %s", timeslot)
            finally:
                self._timeslot_queue.task_done()

    async def _scheduler_worker(self) -> None:
        while True:
            await self._schedule_event.wait()
            self._schedule_event.clear()
            try:
                await self._schedule_once()
            except Exception:
                logging.exception("Work package scheduler failed")

    async def _schedule_once(self) -> None:
        async with self.app.runtime_state_lock:
            core_assignment = self.app.get_core_assigment()
            authorizer_pools = deepcopy(self.app.working_state.authorizer_pools)

        if core_assignment is None:
            return

        async with self._schedule_lock:
            if core_assignment in self._active_cores:
                return

            for h, w in self._pending_work_packages.items():
                if w.status.enum_value()[0] != 'Reportable':
                    continue
                if not authorizer_pools.is_authorized(w.work_package, core_assignment):
                    continue

                w.status = WorkPackageStatus(Reporting=True)
                self._active_cores.add(core_assignment)
                self._refine_queue.put_nowait(RefineQueueEntry(core_index=core_assignment, item=w))
                logging.info(f'Added work package {format_hash(w.work_package.hash())} to worker queue')
                return

    async def _publish_work_package_status(self, wp_item: WorkPackageQueueItem) -> None:
        status_kind = wp_item.status.enum_value()[0]
        status_data = {
            "work_package_hash": wp_item.work_package.hash(),
            "anchor": wp_item.work_package.context.anchor,
            "status": wp_item.status.to_json(),
        }
        if self.app.pubsub:
            await self.app.pubsub.publish_and_wait(
                PubSubSignal(
                    topic=MESSAGE_TYPES.WORK_PACKAGE_STATUS,
                    data=status_data,
                )
            )

        if status_kind == "Reported":
            report_hash = wp_item.work_report.hash() if wp_item.work_report else bytes(32)
            logging.info(
                "cycle_event=reported_status_sent "
                f"work_package={wp_item.work_package.hash().hex()} report={report_hash.hex()}"
            )

    async def _refine_worker(self) -> None:
        while True:
            entry = await self._refine_queue.get()
            wp_item = entry.item
            core_assignment = entry.core_index
            released_core = False

            try:
                logging.info(f'👨‍💻 Processing work-package {format_hash(wp_item.work_package.hash())} [{wp_item.status.enum_value()[0]}]')
                logging.info(
                    "cycle_event=refine_started "
                    f"work_package={wp_item.work_package.hash().hex()} core={core_assignment}"
                )

                # if self.get_core_assigment() is None:
                #     raise ProcessWorkpackageError("Cannot process work package: no core assignment")

                work_package = wp_item.work_package

                # Prepare extrinsic data (GP-0.7.2-eq:B.6 bold_x_flat)
                extrinsics = [
                    [self._work_package_extrinsics.get(work_package, x.hash, x.len) for x in w.extrinsic]
                    for w in work_package.items
                ]

                async with self.app.runtime_state_lock:
                    services_snapshot = deepcopy(self.app.working_state.services)
                    reported_slot = self.app.working_state.timeslot.number
                    reported_header_hash = self.app.retrieve_block_hash(reported_slot)
                    own_validator_index = self.app.get_author_index()
                    own_ed25519 = self.app.config.keys.ed25519.public_key
                    other_validator_indices = [
                        v_idx
                        for v_idx, assignment in enumerate(self.app.block_context.guarantor_assignments)
                        if assignment.validator_ed25519 != own_ed25519 and assignment.core_index == core_assignment
                    ]

                    # Set code from a stable service snapshot.
                    work_package.set_authorization_code(services_snapshot)

                # Todo move work_result_computation to here
                work_report = await anyio.to_thread.run_sync(
                    self.app.work_result_computation,
                    work_package,
                    core_assignment,
                    services_snapshot,
                    extrinsics,
                )

                logging.info(f'👨‍💻Created work-report {format_hash(work_report.hash())}')
                logging.info(
                    "cycle_event=work_report_created "
                    f"work_package={work_package.hash().hex()} report={work_report.hash().hex()}"
                )

                wp_item.work_report = work_report

                # Update work package status
                wp_item.status = WorkPackageStatus(
                    Reported=WorkPackageReportedStatus(
                        reported_in=BlockDesc(
                            slot=reported_slot,
                            header_hash=reported_header_hash
                        ),
                        core=core_assignment,
                        report_hash=work_report.hash()
                    )
                )

                await self._publish_work_package_status(wp_item)

                # Clean up work package extrinsics before the next cycle can reuse memory.
                self._work_package_extrinsics.clear(work_package)

                self._post_report_queue.put_nowait(
                    PostReportQueueEntry(
                        work_package_hash=work_package.hash(),
                        work_report=work_report,
                        own_validator_index=own_validator_index,
                        other_validator_indices=other_validator_indices,
                    )
                )
                await self._release_core(core_assignment)
                released_core = True

                DEBUG and logging.debug(f"Processed work package: {format_hash(work_package.hash())}")
            except Exception as exc:
                logging.exception(f"Error processing work package {format_hash(wp_item.work_package.hash())}")
                wp_item.status = WorkPackageStatus(Failed=str(exc))
                try:
                    await self._publish_work_package_status(wp_item)
                except Exception:
                    logging.exception("Failed to publish failed work-package status")
                self._work_package_extrinsics.clear(wp_item.work_package)
            finally:
                if not released_core:
                    await self._release_core(core_assignment)
                self._refine_queue.task_done()

    async def _post_report_worker(self) -> None:
        while True:
            post_item = await self._post_report_queue.get()
            try:
                logging.info(
                    "cycle_event=post_report_work_started "
                    f"work_package={post_item.work_package_hash.hex()} report={post_item.work_report.hash().hex()}"
                )
                payload = b"jam_guarantee" + blake2b_256_hash(post_item.work_report.to_jam_bytes().to_bytes())
                credential = Credential(
                    validator_index=post_item.own_validator_index,
                    signature=self.app.config.keys.ed25519.sign(payload),
                )
                await self.add_signature(post_item.work_package_hash, credential)

                # TODO exchange signatures with other core members. Local benchmark mode still synthesizes them.
                for validator_index in post_item.other_validator_indices:
                    validator_keys = Keys.from_seed(validator_index.to_bytes(4, 'little') * 8)
                    await self.add_signature(
                        post_item.work_package_hash,
                        Credential(
                            validator_index=validator_index,
                            signature=validator_keys.ed25519.sign(payload),
                        )
                    )
            except Exception:
                logging.exception("Post-report work failed for %s", format_hash(post_item.work_package_hash))
            finally:
                self._post_report_queue.task_done()


    async def _guarantuee_worker(self) -> None:
        while True:
            wp_hash = await self._guarantee_queue.get()
            try:
                if wp_hash in self._guaranteed_work_packages:
                    continue

                wp_item = self._pending_work_packages[wp_hash]

                DEBUG and logging.debug(f'Checking signature for guarantee {format_hash(wp_hash)}')
                if wp_item.work_report and len(wp_item.signatures) >= 2:
                    DEBUG and logging.debug(f'Work-report {format_hash(wp_item.work_report.hash())} has {len(wp_item.signatures)} signatures')

                    if len(wp_item.signatures) == 2:
                        # Enter grace period to wait for final core member to complete work
                        await asyncio.sleep(GUARANTEE_SIGNATURE_WAIT_PERIOD)
                        DEBUG and logging.debug(f'Waiting for third')

                    if wp_hash in self._guaranteed_work_packages:
                        continue

                    # Ingest guarantee extrinsic
                    guarantee = Guarantee(
                        report=wp_item.work_report,
                        slot=self.app.current_timeslot(),
                        signatures=list(wp_item.signatures)
                    )

                    DEBUG and logging.debug(f'Ingested guarantee extrinsic with {len(wp_item.signatures)} signatures')
                    # TODO move to accumulate pipeline?
                    async with self.app.block_extrinsic_lock:
                        self.app.block_extrinsic.add_guarantee(guarantee)
                    self._guaranteed_work_packages.add(wp_hash)
                    logging.info(
                        f'🧾 Added guarantee for work-report {format_hash(wp_item.work_report.hash())} '
                        f'with {len(wp_item.signatures)} signatures'
                    )
                    logging.info(
                        "cycle_event=guarantee_added "
                        f"work_package={wp_hash.hex()} report={wp_item.work_report.hash().hex()}"
                    )
            except Exception:
                logging.exception("Guarantee worker failed for %s", format_hash(wp_hash))
            finally:
                self._guarantee_queue.task_done()

    async def _assurances_worker(self) -> None:
        while True:
            wp_item = await self._assurances_queue.get()

            DEBUG and logging.debug(f'Checking D3L for wp={format_hash(wp_item.work_report.hash())}')

            # TODO implement
