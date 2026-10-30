import os
import asyncio
import logging

import typing
from typing import Optional

from pyjamaz.availability import BundleData
from pyjamaz.exceptions import BlockValidationError, ProcessWorkpackageError, StateTransitionError
from pyjamaz.models.block import AncestorReference
from pyjamaz.models.state import PendingChanges, ServicesState
from pyjamaz.refinement import Refinement
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import InMemoryStorageEngine
from pyjamaz.settings import APP_VERSION, GP_VERSION, FUZZER_VERSION, FUZZER_FEATURE_FORK, FUZZER_FEATURE_ANCESTRY, \
    FUZZER_FEATURE_REFINE, TEST_SUITE
from pyjamaz.fuzzer.v1.types import FuzzerMessage, PeerInfoMessage, Version, Features
from pyjamaz.utils import format_hash


if typing.TYPE_CHECKING:
    from pyjamaz.app import PyjamazApp


class FuzzerTarget:

    def __init__(self, path: str, app: 'PyjamazApp') -> None:
        self.path = path
        self.app = app
        self._refine_head_hash: Optional[bytes] = None

        # Wipe any stale socket first
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass
        self.server: Optional[asyncio.AbstractServer] = None


    def msg_get_state(self, block_hash: Optional[bytes] = None) -> FuzzerMessage:
        return FuzzerMessage(
            # Read the requested posterior state without changing the selected
            # branch. Unavailable states raise and close the protocol session.
            state=(self.app.state_storage.as_list_at(block_hash)
                   if block_hash is not None else self.app.state_storage.as_list())
        )


    async def msg_initialize(self, req: FuzzerMessage) -> FuzzerMessage:
        initial_header = req.initialize.header
        initial_hash = bytes(initial_header.hash)
        if any(bytes(ancestor.header_hash) == initial_hash
               and ancestor.slot != initial_header.timeslot
               for ancestor in req.initialize.ancestry):
            raise ValueError("initialization header ancestry slot mismatch")

        # Flush DB
        for key, _ in self.app.state_db.as_list():
            self.app.state_db.delete(key)

        logging.debug(f"State DB flushed")

        # Update state from received initialize message
        for k, v in req.initialize.state:
            self.app.state_db.put(bytes(k), bytes(v))

        logging.debug(f"Provided state DB keyvals inserted")

        # Clear working state
        self.app.working_state = None

        # Clear state storage
        self.app.state_storage.clear()
        self.app.state_storage.set_finalized_header(req.initialize.header)

        # Process supplied ancestors
        if len(req.initialize.ancestry) > 0:
            parent_hash = bytes(32)
            for ancestor in req.initialize.ancestry[::-1]:
                # Hash/slot hints do not supply a header's state commitments.
                if bytes(ancestor.header_hash) == initial_hash:
                    # The protocol includes this hash in ancestry. Retain the
                    # real header, including its prior-state commitment.
                    ancestor_header = initial_header
                else:
                    ancestor_header = AncestorReference(
                        hash=bytes(ancestor.header_hash),
                        parent=parent_hash,
                        timeslot=ancestor.slot,
                    )

                # Add to ancestry
                self.app.state_storage.add_ancestor(ancestor_header)
                parent_hash = ancestor.header_hash

        # Initialize working state to finalized
        await self.app.initialize()
        self._refine_head_hash = req.initialize.header.hash

        logging.info(f"💾 Initialized state to {format_hash(self.app.working_state.state_root)}")
        return FuzzerMessage(state_root=self.app.working_state.state_root)

    def msg_handshake(self) -> FuzzerMessage:
        return FuzzerMessage(
            peer_info=PeerInfoMessage(
                fuzz_version=FUZZER_VERSION,
                features=Features(fork=FUZZER_FEATURE_FORK, ancestry=FUZZER_FEATURE_ANCESTRY,
                                  refine=FUZZER_FEATURE_REFINE),
                app_version=Version.from_str(APP_VERSION),
                jam_version=Version.from_str(GP_VERSION),
                name = "PyJAMaz"
            )
        )

    async def msg_import_block(self, req: FuzzerMessage, *, ancestry_enabled: Optional[bool] = None):
        if ancestry_enabled is None:
            ancestry_enabled = self.msg_handshake().peer_info.features.block_ancestry
        override = self.app.app_context.skip_lookup_anchor_ancestry
        # Disable ancestry checks if fuzzer feature does not exist
        token = override.set(not ancestry_enabled)

        try:
            # SIMPLE_FORKING imports against any retained parent. Finalizing
            # here would prune ancestry and competing branches before import.
            await self.app.import_block(req.import_block)
            self._refine_head_hash = req.import_block.header.hash

            logging.info(f"✅ Block {format_hash(req.import_block.header.hash)} imported -> state root: {format_hash(self.app.working_state.state_root)}")
            return FuzzerMessage(state_root=self.app.working_state.state_root)

        except (StateTransitionError, BlockValidationError) as e:
            # The application already discarded the candidate and restored its
            # selected state; another rollback could discard that retained state.
            logging.info(f"🛑 Block {format_hash(req.import_block.header.hash)} raised error -> {e}")
            return FuzzerMessage(error=str(e))
        finally:
            override.reset(token)

    async def msg_refine_bundle(self, req: FuzzerMessage) -> FuzzerMessage:
        if self._refine_head_hash is None:
            raise RuntimeError("RefineBundle requires initialization")

        # Detach historical lookups from mutable branch selection and PVM caches.
        engine = InMemoryStorageEngine()
        for key, value in self.app.state_storage.as_list_at(self._refine_head_hash):
            engine.put(key, value)
        services = ServicesState(services={})
        services.set_state_storage(StateStorage(engine))
        services.pending_changes = PendingChanges()
        request = req.refine_bundle
        bundle = request.bundle

        def compute():
            data = BundleData.from_parts(
                bundle.work_package, bundle.extrinsics, bundle.import_segments, bundle.justifications,
            )
            return Refinement(services, data).compute_work_report(
                bundle.work_package, request.core_index, request.segment_root_lookup, request.erasure_shards,
            )

        try:
            return FuzzerMessage(work_report=await asyncio.to_thread(compute))
        except ProcessWorkpackageError as exc:
            # Consensus-defined bundle/Ξ failures leave the session available.
            return FuzzerMessage(error=str(exc))


    async def start(self) -> None:
        self.server = await asyncio.start_unix_server(self._handle_client, path=self.path)
        addr = self.server.sockets[0].getsockname()
        logging.info(f'🥋 PyJAMaz JAM v{APP_VERSION} [Fuzzer target v{FUZZER_VERSION}]')
        logging.info(f"🌐 Listening on {addr}")
        logging.info(f'🧾 Graypaper version: {GP_VERSION} ')
        logging.info(f'🔣 Fuzzer spec: {TEST_SUITE} ')

        async with self.server:
            await self.server.serve_forever()


    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        logging.info(f"[fuzzer] Accepted connection from {peer}")
        try:
            # Handshake: wait for their PeerInfo first.
            them = await FuzzerMessage.fuzzer_decode(reader)
            if them.peer_info is None:
                raise RuntimeError("Expected PeerInfo before requests")
            ours = self.msg_handshake()
            if (them.peer_info.fuzz_version != ours.peer_info.fuzz_version
                    or them.peer_info.jam_version != ours.peer_info.jam_version):
                raise RuntimeError("PeerInfo protocol version mismatch")
            features = ours.peer_info.features & them.peer_info.features
            initialized = False

            writer.write(ours.fuzzer_encode())
            await writer.drain()
            logging.info(
                f"[fuzzer] Handshake complete with {them.peer_info.name} (v{them.peer_info.app_version})"
            )

            # Main request response loop
            while True:
                try:
                    req = await FuzzerMessage.fuzzer_decode(reader)
                except asyncio.IncompleteReadError:
                    # EOF - fuzzer closed the connection cleanly
                    break
                except Exception as e:
                    logging.error(f"[fuzzer] Decode error: {e}; closing session")
                    break

                try:
                    if req.initialize is not None:
                        if initialized:
                            raise RuntimeError("Duplicate Initialize")
                    elif not initialized:
                        raise RuntimeError("Expected Initialize before requests")
                    if req.peer_info is not None:
                        raise RuntimeError("Unexpected PeerInfo after handshake")
                    rsp = await self._dispatch(req, features=features)
                    if req.initialize is not None:
                        initialized = True
                except Exception as e:
                    logging.error(f"[fuzzer] Handler error for {req}: {e}")
                    break  # blunt termination on malformed/unexpected messages

                writer.write(rsp.fuzzer_encode())
                await writer.drain()
        except Exception as exc:
            logging.error(f"[fuzzer] Session error: {exc}")
        finally:
            writer.close()
            await writer.wait_closed()
            logging.info("[fuzzer] Session finished")


    async def _dispatch(self, req: FuzzerMessage, *, features: Optional[Features] = None,
                        ancestry_enabled: Optional[bool] = None) -> FuzzerMessage:
        """
        Request - response pattern for fuzzer

        Parameters
        ----------
        req: FuzzerMessage

        Returns
        -------
        FuzzerMessage
        """
        if req.peer_info is not None:
            return self.msg_handshake()

        elif req.get_state is not None:
            return self.msg_get_state(req.get_state)

        elif req.initialize is not None:
            return await self.msg_initialize(req)

        elif req.import_block is not None:
            if ancestry_enabled is None and features is not None:
                ancestry_enabled = features.block_ancestry
            return await self.msg_import_block(req, ancestry_enabled=ancestry_enabled)

        elif req.refine_bundle is not None:
            negotiated = features if features is not None else self.msg_handshake().peer_info.features
            if not negotiated.refine:
                raise RuntimeError("Refinement was not negotiated")
            return await self.msg_refine_bundle(req)

        else:
            raise RuntimeError(f"Unknown incoming message {req.to_json()}")
