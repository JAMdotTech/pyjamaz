import asyncio
import logging
from asyncio import TaskGroup
from copy import deepcopy
from typing import Dict, List

import anyio

from pyjamaz.app import PyjamazApp
from pyjamaz.availability import BundleData, DataUnavailable, import_reference, resolve_import_root, validate_work_package
from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.merkle import ConstantDepthMerkleTree
from pyjamaz.refinement import Refinement
from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.runtime.extrinsics import WorkpackageExtrinsicCollector
from pyjamaz.models.common import WorkPackage, WorkPackageStatus, WorkPackageReportableStatus, \
    WorkPackageReportedStatus, BlockDesc, Credential, Guarantee
from pyjamaz.runtime.types import WorkPackageQueueItem
from pyjamaz.settings import DEBUG, GUARANTEE_SIGNATURE_WAIT_PERIOD, SOLO_MODE
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
        work_package = deepcopy(work_package)
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

    def _segment_root_lookup(self, package: WorkPackage, state) -> dict[bytes, bytes]:
        # GP-0.8.0-eq:14.14: the runtime supplies the known package-to-export-root correspondence.
        known = {}
        for block in state.recent_history.recent_blocks:
            known.update({report.hash: report.exports_root for report in block.reported})
        for pending in self._pending_work_packages.values():
            if pending.work_report is not None:
                spec = pending.work_report.package_spec
                known[spec.hash] = spec.exports_root
        mappings = {}
        for item in package.items:
            for entry in item.import_segments:
                if entry.is_work_package_hash and entry.tree_root not in mappings:
                    if entry.tree_root in known:
                        mappings[entry.tree_root] = known[entry.tree_root]
                    elif self.app.d3l_store is not None:
                        mappings[entry.tree_root] = self.app.d3l_store.segment_root_for_package(entry.tree_root)
                    else:
                        raise DataUnavailable("segment-root mapping is unavailable")
        return mappings

    def _bundle_data(self, package: WorkPackage, mappings: dict[bytes, bytes]) -> BundleData:
        extrinsics, segments, proofs = [], [], []
        stored_trees = {}
        for item in package.items:
            for manifest in item.extrinsic:
                blob = self._work_package_extrinsics.get(package, manifest.hash, manifest.len)
                if blob is None:
                    raise DataUnavailable("extrinsic data is unavailable")
                extrinsics.append(blob)
            for entry in item.import_segments:
                root = resolve_import_root(mappings, import_reference(entry))
                if self.app.d3l_store is None:
                    raise DataUnavailable("imported segments are unavailable")
                if root not in stored_trees:
                    stored = self.app.d3l_store.retrieve_segments(root).segments
                    tree = ConstantDepthMerkleTree(stored)
                    if tree.root() != root:
                        raise ProcessWorkpackageError("stored segments do not match their root")
                    stored_trees[root] = (stored, tree)
                stored, tree = stored_trees[root]
                if entry.segment_index >= len(stored):
                    raise ProcessWorkpackageError("import segment index out of range")
                segments.append(stored[entry.segment_index])
                proofs.append(tree.trace(entry.segment_index))
        return BundleData.from_parts(package, extrinsics, segments, proofs)

    @staticmethod
    def _validator_keys(state) -> tuple[bytes, ...]:
        return tuple(bytes(validator.ed25519) for validator in state.validator_pool.validators)

    @staticmethod
    def _view_is_committed(state, head_hash: bytes) -> bool:
        storage = state.services.state_storage
        return not storage.transaction and storage.block_hash in (None, head_hash)

    @staticmethod
    def _retry(item: WorkPackageQueueItem) -> None:
        item.work_report = None
        item.signatures.clear()
        item.status = WorkPackageStatus(Reportable=WorkPackageReportableStatus(remaining_blocks=4))

    async def _refine_worker(self) -> None:
        while True:
            item = await self._refine_queue.get()
            try:
                await self._refine_work_package(item)
            except asyncio.CancelledError:
                self._retry(item)
                raise
            except DataUnavailable as exc:
                self._retry(item)
                logging.info("Refine waits for data: %s", exc)
            except ProcessWorkpackageError as exc:
                self._retry(item)
                item.status = WorkPackageStatus(Failed=str(exc))
                logging.info("Work package rejected: %s", exc)
            except Exception as exc:
                self._retry(item)
                item.status = WorkPackageStatus(Failed=str(exc))
                logging.exception("Work-package refinement failed")
            finally:
                self._refine_queue.task_done()

    async def _refine_work_package(self, item: WorkPackageQueueItem) -> None:
        # Capture every input before dispatch; the worker must not follow a live state view.
        state = self.app.working_state
        package = deepcopy(item.work_package)
        validate_work_package(package)
        core = self.app.get_core_assigment()
        if core is None:
            self._retry(item)
            return
        head_root = state.state_root
        slot = state.timeslot.number
        head_hash = self.app.retrieve_block_hash(slot)
        if head_hash is None or not self._view_is_committed(state, head_hash):
            self._retry(item)
            return
        validator_keys = self._validator_keys(state)
        mappings = self._segment_root_lookup(package, state)
        data = self._bundle_data(package, mappings)
        execution = Refinement(state.services.snapshot(), data)
        report = await anyio.to_thread.run_sync(
            execution.compute_work_report, package, core, mappings, len(validator_keys),
        )

        # A changed branch or validator/core assignment needs a fresh guarantee view.
        current = self.app.working_state
        if (current.state_root != head_root or self.app.get_core_assigment() != core
                or self._validator_keys(current) != validator_keys
                or not self._view_is_committed(current, head_hash)):
            self._retry(item)
            return
        if self.app.d3l_store is not None:
            self.app.d3l_store.store_work_report(report, execution.bundle, execution.exported_segments)
        item.work_report = report
        item.status = WorkPackageStatus(Reported=WorkPackageReportedStatus(
            reported_in=BlockDesc(slot=slot, header_hash=head_hash), core=core, report_hash=report.hash(),
        ))
        if self.app.pubsub:
            await self.app.pubsub.publish(PubSubSignal(
                topic=MESSAGE_TYPES.WORK_PACKAGE_STATUS, data=[item.status.to_json()],
            ))
        credential = await self.app.create_guarantee_signature(report)
        await self.add_signature(package.hash(), credential)

        if SOLO_MODE:
            for index, assignment in enumerate(self.app.block_context.guarantor_assignments):
                if (assignment.validator_ed25519 != self.app.config.keys.ed25519.public_key
                        and assignment.core_index == core):
                    signature = await self.app.create_guarantee_signature_for_validator(report, index)
                    await self.add_signature(package.hash(), signature)
        self._work_package_extrinsics.clear(item.work_package)
        logging.info("Created work-report %s", format_hash(report.hash()))

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
