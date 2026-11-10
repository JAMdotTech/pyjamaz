"""Chapter 14 local/peer data services, composed from GP recovery and verification.

Wire behavior follows JAMNP-S v1 e0b7d291. These services expose data readiness;
they do not produce guarantees, assurance votes or audit judgments.
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass

from jamcodec.base import JamBytes
from jamcodec.exceptions import ScaleDecodeException

from pyjamaz.availability import (
    DataUnavailable, ImportedSegment, audit_shard_justification, import_reference,
    recover_import, resolve_import_root, verify_import, verify_segment_shard,
)
from pyjamaz.bundle import decode_bundle, encode_bundle
from pyjamaz.constants import WELL_KNOWN_STORAGE_KEYS
from pyjamaz.d3l import AvailabilitySource
from pyjamaz.erasure import erasure_data_shards
from pyjamaz.exceptions import ProcessWorkpackageError, StateTransitionError
from pyjamaz.graypaper_constants import (
    EC_SEGMENT_SIZE, EPOCH_TIMESLOTS, MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE, ROTATION_PERIOD_CORE,
)
from pyjamaz.merkle import ConstantDepthMerkleTree
from pyjamaz.models.context import AppContext, BlockContext
from pyjamaz.models.state import AssurancesState, EntropyState, TimeslotState, ValidatorArchiveState, ValidatorPoolState
from pyjamaz.state.components import Assurances


@dataclass
class StagedSubmission:
    authorization: object
    package: object
    mappings: dict[bytes, bytes]


class AvailabilityRuntime:
    REQUEST_TIMEOUT = 5
    REQUESTS_IN_FLIGHT = 4
    BACKFILL_BATCH_SIZE = 64

    def __init__(self, app):
        self.app = app
        self._queue = asyncio.Queue(maxsize=4096)
        self._queued = set()
        self._canonical_head = None
        self._canonical_hashes = set()
        self._canonical_cursor = None
        self._parents = {}
        # Discover ancestors backwards, then replay this queue oldest first.
        self._backfill_pending = deque()
        self._repair_blocks = {}
        self._backfill_wakeup = asyncio.Event()
        self._availability_finalized_hash = None
        self._availability_finalized_blocks = set()

    @property
    def store(self):
        if self.app.d3l_store is None:
            raise DataUnavailable('availability storage is disabled')
        return self.app.d3l_store

    def start(self, task_group):
        task_group.start_soon(self._assigned_worker)
        task_group.start_soon(self._backfill_worker)
        self._backfill_wakeup.set()

    def _head(self):
        storage = self.app.state_storage
        return getattr(storage, 'block_hash', None) or getattr(storage, 'finalized_block_hash', None)

    def _parent(self, block_hash):
        if block_hash not in self._parents:
            header = self.app.retrieve_block_header(block_hash)
            if header is not None:
                self._parents[block_hash] = header.parent
            else:
                parent = getattr(self.app.state_storage, 'parents', {}).get(block_hash)
                # A just-committed header may not yet have reached block storage.
                # Do not cache an absent parent: storage can become available later.
                if parent is not None:
                    self._parents[block_hash] = parent
                return parent
        return self._parents[block_hash]

    def _refresh_canonical_head(self):
        head = self._head()
        if head == self._canonical_head:
            return
        cursor, path = head, []
        while cursor is not None and cursor not in self._canonical_hashes and len(path) < self.BACKFILL_BATCH_SIZE:
            if cursor in path:
                cursor = None
                break
            path.append(cursor)
            cursor = self._parent(cursor)
        if cursor in self._canonical_hashes:
            old = self._canonical_head
            removed = 0
            while old is not None and old != cursor and removed < self.BACKFILL_BATCH_SIZE:
                self._canonical_hashes.discard(old)
                old = self._parents.get(old)
                removed += 1
            if old != cursor:
                # Do not walk an arbitrarily long discarded branch in one call.
                self._canonical_hashes.clear()
                self._canonical_cursor = cursor
                self._backfill_pending.clear()
            self._backfill_pending.extend(reversed(path))
        else:
            # A deep reorganization is discovered in bounded batches just like startup.
            self._canonical_hashes.clear()
            self._canonical_cursor = cursor
            self._backfill_pending.clear()
            self._backfill_pending.extend(reversed(path))
        self._canonical_head = head
        self._canonical_hashes.update(path)
        self._backfill_wakeup.set()

    def _lineage(self, head):
        """Use persisted headers; finalized state overlays need not retain ancestry."""
        seen = set()
        while head is not None and head not in seen:
            seen.add(head)
            head = self._parent(head)
        return seen

    def canonical(self, block_hash):
        self._refresh_canonical_head()
        return block_hash in self._canonical_hashes

    def source_for(self, **lookup):
        try:
            return self.store.source_for(**lookup, canonical=self.canonical)
        except DataUnavailable:
            self._backfill_sources()
            key = next(((kind, value) for kind, value in lookup.items() if value is not None), None)
            # Known registration/assurance blocks can repair a removed record at
            # the same head without rescanning every retained block.
            for block_hash in tuple(self._repair_blocks.get(key, ())):
                if self.canonical(block_hash):
                    self._backfill_block(block_hash)
            return self.store.source_for(**lookup, canonical=self.canonical)

    def _backfill_sources(self):
        """Discover and replay at most one small batch of retained historical context."""
        self._refresh_canonical_head()
        for _ in range(self.BACKFILL_BATCH_SIZE):
            cursor = self._canonical_cursor
            if cursor is None or cursor in self._canonical_hashes:
                self._canonical_cursor = None
                break
            self._canonical_hashes.add(cursor)
            self._backfill_pending.appendleft(cursor)
            self._canonical_cursor = self._parent(cursor)
        if self._canonical_cursor is not None:
            return
        for _ in range(self.BACKFILL_BATCH_SIZE):
            if not self._backfill_pending:
                break
            block_hash = self._backfill_pending.popleft()
            if self.canonical(block_hash):
                try:
                    self._backfill_block(block_hash)
                except OSError:
                    self._backfill_pending.appendleft(block_hash)
                    raise

    async def _backfill_worker(self):
        while True:
            await self._backfill_wakeup.wait()
            self._backfill_wakeup.clear()
            while True:
                try:
                    self._backfill_sources()
                except (OSError, DataUnavailable):
                    logging.exception('Historical availability backfill will retry later')
                    break
                if self._canonical_cursor is None and not self._backfill_pending:
                    break
                await asyncio.sleep(0)

    def _backfill_block(self, block_hash):
        block = self.app.retrieve_block_by_hash(block_hash)
        if block is None or not block.extrinsic.guarantees and not block.extrinsic.assurances:
            return
        # The accepted block identifies the records to retry if its historical
        # state is restored later. These hints do not establish source metadata.
        for guarantee in block.extrinsic.guarantees:
            self._remember_source_block(guarantee.report, block_hash)
        try:
            state = dict(self.app.state_storage.as_list_at(block.header.hash))
            def read(component, codec):
                return codec.from_jam_bytes(JamBytes(state[WELL_KNOWN_STORAGE_KEYS[component]]))
            pool = read(8, ValidatorPoolState)
            archive = read(9, ValidatorArchiveState)
            entropy = read(6, EntropyState)
            timeslot = TimeslotState(block.header.timeslot)
            context = BlockContext()
            context.set_guarantor_assignments(entropy, timeslot, pool)
            context.set_prev_guarantor_assignments(entropy, timeslot, pool, archive)
            self.record_committed(block, pool.validators, archive.validators, context,
                                  self._reported_from_block(block, pool))
        except (KeyError, ValueError, DataUnavailable, ScaleDecodeException, StateTransitionError):
            # Missing historical state must not be replaced with the current validator set.
            return

    def _reported_from_block(self, block, pool):
        if not block.extrinsic.assurances:
            return []
        try:
            # Reuse 10.14 and 11.17-18; disappearing assignments may also be
            # timeouts, disputes or resize, which must not be mistaken for assurance.
            parent_state = dict(self.app.state_storage.as_list_at(block.header.parent))
            prior_pool = ValidatorPoolState.from_jam_bytes(JamBytes(parent_state[WELL_KNOWN_STORAGE_KEYS[8]]))
            pending = AssurancesState.from_jam_bytes(JamBytes(parent_state[WELL_KNOWN_STORAGE_KEYS[10]]))
            rules = Assurances(BlockContext(), AppContext())
            intermediate = rules.state_transition_after_disputes(block.extrinsic.disputes, pending)
            return rules.state_transition_after_assurances(
                block.extrinsic.assurances, intermediate.intermediate_state_after_disputes,
                block.header, prior_pool, pool,
            ).reported
        except (KeyError, ValueError, DataUnavailable, ScaleDecodeException, StateTransitionError):
            return []  # Missing assurance context retains audit payloads conservatively.

    def record_committed(self, block, validators, archived_validators, context, available_reports):
        """Called after commit, while verified guarantee assignment identities are known."""
        if self.app.d3l_store is None:
            return
        self._parents[block.header.hash] = block.header.parent
        self._refresh_canonical_head()
        for guarantee in block.extrinsic.guarantees:
            self._remember_source_block(guarantee.report, block.header.hash)
            current = block.header.timeslot // ROTATION_PERIOD_CORE == guarantee.slot // ROTATION_PERIOD_CORE
            assignments = context.guarantor_assignments if current else context.prev_guarantor_assignments
            previous_epoch = ((block.header.timeslot - ROTATION_PERIOD_CORE) // EPOCH_TIMESLOTS
                              != block.header.timeslot // EPOCH_TIMESLOTS)
            guarantor_set = archived_validators if not current and previous_epoch else validators
            by_key = {v.ed25519: v for v in guarantor_set}
            guarantors = [by_key[assignments[s.validator_index].validator_ed25519]
                          for s in guarantee.signatures]
            source = AvailabilitySource(guarantee.report, list(validators), guarantors,
                                        block.header.hash, block.header.timeslot)
            try:
                source = self.store._source(source.identity)
            except DataUnavailable:
                pass  # The committed context can reconstruct a missing source record.
            self.store.register_source(source)
            self._enqueue(source)
        for report in available_reports:
            self._remember_source_block(report, block.header.hash)
            try:
                self.store.mark_assured(report, block.header.hash, block.header.timeslot, self.canonical)
            except DataUnavailable:
                pass

    def _remember_source_block(self, report, block_hash):
        spec = report.package_spec
        for kind, value in (('package_hash', spec.hash), ('exports_root', spec.exports_root),
                            ('erasure_root', spec.erasure_root)):
            blocks = self._repair_blocks.setdefault((kind, value), deque(maxlen=self.BACKFILL_BATCH_SIZE))
            if block_hash not in blocks:
                blocks.append(block_hash)

    def _enqueue(self, source):
        try:
            self.assigned_index(source)
        except DataUnavailable:
            return
        finalized_hash = self._availability_finalized_hash
        finalized_header = self.app.retrieve_block_header(finalized_hash) if finalized_hash is not None else None
        if (finalized_header is not None
                and finalized_header.timeslot >= source.registered_slot + 672 * EPOCH_TIMESLOTS
                and self._assurance_finalized(source)):
            return  # Local retention expiry does not affect report validity or import eligibility.
        if source.identity not in self._queued:
            try:
                self._queue.put_nowait(source)
                self._queued.add(source.identity)
            except asyncio.QueueFull:
                logging.info('Availability acquisition queue is full; retry at the next slot')

    def retry_assigned(self):
        self._backfill_sources()
        for source in self.store.sources():
            if self.canonical(source.registered_block):
                self._enqueue(source)

    async def _assigned_worker(self):
        while True:
            source = await self._queue.get()
            try:
                await self.acquire_assigned(source)
            except (DataUnavailable, ProcessWorkpackageError):
                logging.debug('Assigned availability data is not ready', exc_info=True)
            except asyncio.CancelledError:
                raise
            except Exception:
                logging.exception('Assigned availability acquisition failed')
            finally:
                self._queued.discard(source.identity)
                self._queue.task_done()

    def on_finalized(self, block_hash):
        # Only the application's explicitly confirmed finality path calls this hook.
        # Repeated or delayed confirmations must not move trusted availability finality backwards.
        if block_hash not in self._availability_finalized_blocks:
            self._availability_finalized_hash = block_hash
            self._availability_finalized_blocks = self._lineage(block_hash)
        block_hash = self._availability_finalized_hash
        header = self.app.retrieve_block_header(block_hash)
        if header is not None:
            self.store.prune(header.timeslot, self.canonical, self._availability_finalized_blocks.__contains__)

    def assigned_index(self, source):
        key = self.app.config.keys.ed25519.public_key
        for validator_index, validator in enumerate(source.validators):
            if validator.ed25519 == key:
                # JAMNP-S-e0b7d291:CE137: i=(c*D(v)+validator_index) mod v.
                return (source.report.core_index * erasure_data_shards(source.spec.erasure_shards)
                        + validator_index) % source.spec.erasure_shards
        raise DataUnavailable('this node was not an assurer of the source report')

    def assigned_ready(self, source):
        try:
            index = self.assigned_index(source)
            if self._assurance_finalized(source):
                self.store._row(source.spec, index)
            else:
                self.store.retrieve_validator_shard(source.spec, index)
            return True
        except DataUnavailable:
            return False

    def _assurance_finalized(self, source):
        return source.assured_block is not None and source.assured_block in self._availability_finalized_blocks

    async def _request(self, method, *args, **kwargs):
        protocol = getattr(self.app, 'protocol', None)
        if protocol is None:
            raise DataUnavailable('availability transport is not started')
        try:
            async with asyncio.timeout(self.REQUEST_TIMEOUT):
                return await getattr(protocol, method)(*args, **kwargs)
        except (TimeoutError, OSError, ConnectionError, ValueError) as exc:
            raise DataUnavailable('availability peer request failed') from exc

    async def acquire_assigned(self, source):
        if not self.canonical(source.registered_block):
            raise DataUnavailable('source is no longer on the active branch')
        index = self.assigned_index(source)
        if self.assigned_ready(source):
            return
        with self.store.hold(source.spec.erasure_root):
            for peer in source.guarantors:
                try:
                    shard = await self._request('request_validator_shard', peer, source.spec, index)
                    if shard.shard_index != index:
                        raise DataUnavailable('peer returned a different assigned shard')
                    if not self.canonical(source.registered_block):
                        raise DataUnavailable('source branch changed during acquisition')
                    self.store.store_validator_shard(source.spec, shard)
                    return
                except (DataUnavailable, ProcessWorkpackageError):
                    continue
        raise DataUnavailable('assigned shard is unavailable')

    async def acquire_package_imports(self, package, mappings):
        # GP-0.8.0-eq:14.15: one acquisition per (root,index); BundleData restores manifest order.
        needed = {(resolve_import_root(mappings, import_reference(entry)), entry.segment_index)
                  for item in package.items for entry in item.import_segments}
        page_cache = {}
        for root, index in sorted(needed):
            try:
                self._local_import(root, index)
            except DataUnavailable:
                await self.acquire_import(root, index, page_cache=page_cache)

    def _local_import(self, root, index):
        try:
            return self.store.retrieve_import(root, index)
        except DataUnavailable:
            stored = [bytes(segment) for segment in self.store.retrieve_segments(root).segments]
            tree = ConstantDepthMerkleTree(stored)
            if tree.root() != root:
                raise DataUnavailable('stored export segments do not match their root')
            if not 0 <= index < len(stored):
                raise ProcessWorkpackageError('import segment index out of range')
            imported = ImportedSegment(stored[index], tuple(tree.trace(index)))
            try:
                verify_import(root, index, imported)
            except ProcessWorkpackageError as exc:
                raise DataUnavailable('stored export segment is invalid') from exc
            return imported

    async def acquire_import(self, root, index, *, page_cache=None):
        try:
            return self._local_import(root, index)
        except DataUnavailable:
            pass
        source = self.source_for(exports_root=root)
        spec = source.spec
        if not 0 <= index < spec.exports_count:
            raise ProcessWorkpackageError('import segment index out of range')
        with self.store.hold(spec.erasure_root):
            for peer in source.guarantors:
                try:
                    imports = await self._request('request_segments', peer, root, [index])
                    if len(imports) != 1:
                        raise DataUnavailable('incorrect complete-segment response count')
                    imported = imports[0]
                    verify_import(root, index, imported)
                    return self._store_acquired(source, index, imported)
                except (DataUnavailable, ProcessWorkpackageError):
                    continue
            # JAMNP-S-e0b7d291:CE139/140: fast reconstruction, then individually proven retry.
            for proven in (False, True):
                imported = await self._coded_import(source, index, proven, page_cache)
                if imported is not None:
                    return self._store_acquired(source, index, imported)
        raise DataUnavailable('not enough source shards to recover the import')

    def _store_acquired(self, source, index, imported):
        if not self.canonical(source.registered_block):
            raise DataUnavailable('source branch changed during recovery')
        self.store.store_import(source.spec.exports_root, index, imported)
        return imported

    async def _coded_import(self, source, index, proven, page_cache):
        spec = source.spec
        threshold = erasure_data_shards(spec.erasure_shards)
        page_index = spec.exports_count + index // 64
        page_key = (source.identity, page_index, proven)
        pages = dict((page_cache or {}).get(page_key, {}))
        chunks = {}
        semaphore = asyncio.Semaphore(self.REQUESTS_IN_FLIGHT)

        async def fetch(shard_index):
            # Invert the report's assignment; historical endpoints come from its original set.
            owner = (shard_index - source.report.core_index * threshold) % spec.erasure_shards
            indices = [index] if shard_index in pages else [index, page_index]
            try:
                async with semaphore:
                    values = await self._request('request_segment_shards', source.validators[owner], spec,
                                                 shard_index, indices, proven=proven)
                if len(values) != len(indices):
                    return None
                for segment_index, (chunk, proof) in zip(indices, values):
                    if proven:
                        verify_segment_shard(chunk, segment_index, shard_index, proof, spec)
                return shard_index, dict(zip(indices, [chunk for chunk, _ in values]))
            except (DataUnavailable, ProcessWorkpackageError, ValueError):
                return None

        # Only four live tasks. Stop outstanding requests as soon as a threshold is available.
        remaining = iter(range(spec.erasure_shards))
        pending = set()
        def schedule():
            for _ in range(self.REQUESTS_IN_FLIGHT - len(pending)):
                shard_index = next(remaining, None)
                if shard_index is not None:
                    pending.add(asyncio.create_task(fetch(shard_index)))
        schedule()
        try:
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    result = task.result()
                    if result is not None:
                        shard_index, values = result
                        chunks[shard_index] = values[index]
                        if page_index in values:
                            pages[shard_index] = values[page_index]
                if len(chunks) >= threshold and len(pages) >= threshold:
                    try:
                        imported = recover_import(spec, index, chunks, proof_page_shards=pages)
                    except ProcessWorkpackageError:
                        if proven:
                            raise ProcessWorkpackageError('individually proven shards contradict the source commitment')
                        return None
                    if page_cache is not None:
                        page_cache[page_key] = pages
                    return imported
                schedule()
        finally:
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        return None

    async def authorize_submission(self, peer_key, core_index, package, mappings):
        pipeline = self.app.runtime.refine_pipeline
        authorization = await pipeline.authorize_submission(core_index, package)
        known = pipeline._segment_root_lookup(package, self.app.working_state)
        if mappings and mappings != known:
            raise ProcessWorkpackageError('submitted mappings conflict with known reports')
        return StagedSubmission(authorization, package, known)

    async def complete_submission(self, context, kind, messages):
        from pyjamaz.transport.jamnp_messages import decode_import_proofs

        pipeline = self.app.runtime.refine_pipeline
        if not pipeline._authorization_current(context.authorization, context.package):
            raise DataUnavailable('submission authorization became stale')
        package = context.package
        # The transport supplies only the remaining payloads, after the authorized prefix.
        if kind == 133:
            if len(messages) != 1 or any(item.import_segments for item in package.items):
                raise ProcessWorkpackageError('CE133 requires an import-free package')
            extrinsic_bytes, segment_bytes, proofs = messages[0], b'', []
        elif kind == 146:
            if len(messages) != 3:
                raise ProcessWorkpackageError('incomplete CE146 submission')
            extrinsic_bytes, segment_bytes = messages[:2]
            proofs = decode_import_proofs(messages[2], sum(len(item.import_segments) for item in package.items))
        else:
            raise ProcessWorkpackageError('unsupported submission stream')
        extrinsics, offset = [], 0
        for item in package.items:
            for entry in item.extrinsic:
                extrinsics.append(extrinsic_bytes[offset:offset + entry.len])
                offset += entry.len
        if offset != len(extrinsic_bytes) or len(segment_bytes) % EC_SEGMENT_SIZE:
            raise ProcessWorkpackageError('invalid submitted data lengths')
        segments = [segment_bytes[start:start + EC_SEGMENT_SIZE]
                    for start in range(0, len(segment_bytes), EC_SEGMENT_SIZE)]
        try:
            raw = encode_bundle(package, extrinsics, segments, proofs)
            parts = decode_bundle(raw)
            from pyjamaz.availability import BundleData
            data = BundleData.from_parts(package, parts.extrinsics, parts.segments, parts.justifications)
            data.assemble_bundle(package, context.mappings)
        except ValueError as exc:
            raise ProcessWorkpackageError(str(exc)) from exc
        pipeline.add_work_package(package, extrinsics, core_index=context.authorization.core_index,
                                  bundle=raw, authorization_context=context.authorization)
        return []

    def _authorize_read(self, peer_key, spec):
        try:
            source = self.source_for(erasure_root=spec.erasure_root)
            participants = source.validators + source.guarantors
        except DataUnavailable:
            # Locally generated data is served to its current assurers before report registration.
            participants = self.app.working_state.validator_pool.validators
        if peer_key not in {v.ed25519 for v in participants}:
            raise ProcessWorkpackageError('peer is not a participant in the source report')

    async def handle_request(self, peer_key, kind, messages):
        from pyjamaz.transport.jamnp_messages import (
            decode_segment_indices, decode_segment_requests, encode_import_proofs, encode_justification,
        )

        if len(messages) != 1:
            raise ProcessWorkpackageError('availability request requires one message')
        request = messages[0]
        if kind in (137, 138, 147):
            if len(request) != (32 if kind == 147 else 34):
                raise ProcessWorkpackageError('invalid shard request length')
            spec = self.store.specification(request[:32], self.canonical)
            self._authorize_read(peer_key, spec)
            with self.store.hold(spec.erasure_root):
                if kind == 147:
                    return [self.store._retrieve(b'bundle:' + spec.hash, 'audit bundle is unavailable')]
                index = int.from_bytes(request[32:], 'little')
                shard = self.store.retrieve_validator_shard(spec, index)
                if kind == 137:
                    return [shard.bundle_shard, b''.join(shard.segment_shards), encode_justification(shard.justification)]
                return [shard.bundle_shard, encode_justification(audit_shard_justification(shard))]
        if kind in (139, 140):
            groups = decode_segment_requests(request)
            if sum(len(indices) for _, _, indices in groups) > 2 * MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE:
                raise ProcessWorkpackageError('too many requested segment chunks')
            chunks, proofs = [], []
            for root, shard_index, indices in groups:
                spec = self.store.specification(root, self.canonical)
                self._authorize_read(peer_key, spec)
                with self.store.hold(root):
                    for index in indices:
                        chunk, proof = self.store.retrieve_segment_shard(spec, shard_index, index)
                        chunks.append(chunk)
                        if kind == 140:
                            proofs.append(encode_justification(proof, EC_SEGMENT_SIZE // erasure_data_shards(spec.erasure_shards)))
            return [b''.join(chunks)] + proofs
        if kind == 148:
            groups = decode_segment_indices(request)
            if sum(len(indices) for _, indices in groups) > MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE:
                raise ProcessWorkpackageError('too many requested segments')
            imports = []
            for root, indices in groups:
                source = self.source_for(exports_root=root)
                self._authorize_read(peer_key, source.spec)
                with self.store.hold(source.spec.erasure_root):
                    imports.extend(self._local_import(root, index) for index in indices)
            return [b''.join(item.segment for item in imports),
                    encode_import_proofs([item.justification for item in imports])]
        raise ProcessWorkpackageError('unsupported availability stream')
