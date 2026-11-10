import asyncio
import logging
from asyncio import TaskGroup
from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, List

import anyio

from pyjamaz.app import PyjamazApp
from pyjamaz.availability import BundleData, DataUnavailable, import_reference, resolve_import_root, validate_work_package
from pyjamaz.bundle import decode_bundle
from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.graypaper_constants import CORE_COUNT
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


@dataclass
class AuthorizedSubmission:
    """Local Psi_I result bound to the exact inputs used for a Refine attempt."""
    package_hash: bytes
    core_index: int
    head_hash: bytes
    head_root: bytes
    validator_keys: tuple[bytes, ...]
    services: object
    authorization: object


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

    def add_work_package(self, work_package: WorkPackage, extrinsics: List[bytes], *,
                         core_index: int | None = None, bundle: bytes | None = None,
                         authorization_context: AuthorizedSubmission | None = None):
        if core_index is not None and (isinstance(core_index, bool) or not isinstance(core_index, int)
                                       or not 0 <= core_index < CORE_COUNT):
            raise ProcessWorkpackageError("invalid core index")
        work_package = deepcopy(work_package)
        self._pending_work_packages[work_package.hash()] = WorkPackageQueueItem(
            work_package=work_package, status=WorkPackageStatus(
                Reportable=WorkPackageReportableStatus(
                    remaining_blocks=4
                    )
                ), core_index=core_index, bundle=bundle,
            )

        self._pending_work_packages[work_package.hash()].authorization_context = authorization_context

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
                        if w.core_index is not None and w.core_index != self.app.get_core_assigment():
                            continue
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
                        availability = getattr(getattr(self.app, 'runtime', None), 'availability', None)
                        if availability is not None:
                            # Historical mappings become authoritative only through accepted reports.
                            mappings[entry.tree_root] = availability.source_for(package_hash=entry.tree_root).spec.exports_root
                        else:
                            mappings[entry.tree_root] = self.app.d3l_store.segment_root_for_package(entry.tree_root)
                    else:
                        raise DataUnavailable("segment-root mapping is unavailable")
        return mappings

    def _bundle_data(self, package: WorkPackage, mappings: dict[bytes, bytes]) -> BundleData:
        # GP-0.8.0-eq:14.15-14.16: acquire S_l(w) and J_l(w) in manifest order for B(p,l).
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
                try:
                    imported = self.app.d3l_store.retrieve_import(root, entry.segment_index)
                except DataUnavailable:
                    pass
                else:
                    segments.append(imported.segment)
                    proofs.append(imported.justification)
                    continue
                if root not in stored_trees:
                    stored = self.app.d3l_store.retrieve_segments(root).segments
                    tree = ConstantDepthMerkleTree(stored)
                    if tree.root() != root:
                        raise DataUnavailable("stored segments do not match their root")
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
        item.authorization_context = None
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

    async def authorize_submission(self, core_index: int, package: WorkPackage) -> AuthorizedSubmission:
        """Authorize a staged submission before its extrinsics/import messages are received."""
        state = self.app.working_state
        if core_index != self.app.get_core_assigment():
            raise ProcessWorkpackageError("work package targets an unassigned core")
        head_hash = self.app.retrieve_block_hash(state.timeslot.number)
        if head_hash is None or not self._view_is_committed(state, head_hash):
            raise DataUnavailable("refinement state is not committed")
        keys = self._validator_keys(state)
        root = state.state_root
        services = state.services.snapshot()
        owned_package = deepcopy(package)
        execution = Refinement(services, BundleData())
        authorization = await asyncio.to_thread(execution.authorize, owned_package, core_index)
        context = AuthorizedSubmission(package.hash(), core_index, head_hash, root, keys, services, authorization)
        if not self._authorization_current(context, package):
            raise DataUnavailable("refinement state changed during authorization")
        return context

    def _authorization_current(self, context: AuthorizedSubmission, package: WorkPackage) -> bool:
        state = self.app.working_state
        return (context.package_hash == package.hash()
                and context.core_index == self.app.get_core_assigment()
                and context.head_hash == self.app.retrieve_block_hash(state.timeslot.number)
                and context.head_root == state.state_root
                and context.validator_keys == self._validator_keys(state)
                and self._view_is_committed(state, context.head_hash))

    async def _refine_work_package(self, item: WorkPackageQueueItem) -> None:
        # Capture every input before dispatch; the worker must not follow a live state view.
        state = self.app.working_state
        package = deepcopy(item.work_package)
        validate_work_package(package)
        core = self.app.get_core_assigment()
        if core is None or (item.core_index is not None and item.core_index != core):
            self._retry(item)
            return
        head_root = state.state_root
        slot = state.timeslot.number
        head_hash = self.app.retrieve_block_hash(slot)
        if head_hash is None or not self._view_is_committed(state, head_hash):
            self._retry(item)
            return
        validator_keys = self._validator_keys(state)
        context = item.authorization_context
        if context is not None and self._authorization_current(context, package):
            execution = Refinement(context.services, BundleData())
            authorization = context.authorization
        else:
            execution = Refinement(state.services.snapshot(), BundleData())
            authorization = await asyncio.to_thread(execution.authorize, package, core)
        # GP-0.8.0-eq:14.13: Psi_I has succeeded before X/S_l/J_l acquisition.
        mappings = self._segment_root_lookup(package, state)
        if item.bundle is not None:
            try:
                parts = decode_bundle(item.bundle)
                if parts.package != package:
                    raise ValueError("bundle package differs from queued package")
                data = BundleData.from_parts(package, parts.extrinsics, parts.segments, parts.justifications)
            except ValueError as exc:
                raise ProcessWorkpackageError(str(exc)) from exc
        else:
            try:
                data = self._bundle_data(package, mappings)
            except DataUnavailable:
                availability = getattr(getattr(self.app, 'runtime', None), 'availability', None)
                if availability is None:
                    raise
                await availability.acquire_package_imports(package, mappings)
                data = self._bundle_data(package, mappings)
        execution.data = data
        report = await anyio.to_thread.run_sync(
            execution._compute_authorized_report, package, core, mappings, len(validator_keys), authorization,
        )

        # A changed branch or validator/core assignment needs a fresh guarantee view.
        current = self.app.working_state
        if (current.state_root != head_root or self.app.get_core_assigment() != core
                or self._validator_keys(current) != validator_keys
                or not self._view_is_committed(current, head_hash)):
            self._retry(item)
            return
        if self.app.d3l_store is not None:
            self.app.d3l_store.store_work_report(report, execution.bundle, execution.exported_segments,
                                               artifacts=execution.artifacts)
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
