import os
import asyncio
import logging

import typing
from typing import Optional

from pyjamaz.exceptions import BlockValidationError, StateTransitionError
from pyjamaz.models.block import Header
from pyjamaz.settings import APP_VERSION, GP_VERSION, FUZZER_VERSION, FUZZER_FEATURE_FORK, FUZZER_FEATURE_ANCESTRY
from pyjamaz.fuzzer.v1.types import FuzzerMessage, PeerInfoMessage, Version, Features
from pyjamaz.utils import format_hash


if typing.TYPE_CHECKING:
    from pyjamaz.app import PyjamazApp


class FuzzerTarget:

    def __init__(self, path: str, app: 'PyjamazApp') -> None:
        self.path = path
        self.app = app

        # Wipe any stale socket first
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass
        self.server: Optional[asyncio.AbstractServer] = None


    def msg_get_state(self) -> FuzzerMessage:
        return FuzzerMessage(
            state=self.app.state_db.as_list()
        )


    async def msg_initialize(self, req: FuzzerMessage) -> FuzzerMessage:
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
                # Create header
                ancestor_header = Header.default()
                ancestor_header.hash = ancestor.header_hash
                ancestor_header.parent = parent_hash

                # Add to ancestry
                self.app.state_storage.add_ancestor(ancestor_header)
                parent_hash = ancestor.header_hash

        # Initialize working state to finalized
        await self.app.initialize()

        logging.info(f"💾 Initialized state to {format_hash(self.app.working_state.state_root)}")
        return FuzzerMessage(state_root=self.app.working_state.state_root)

    def msg_handshake(self) -> FuzzerMessage:
        return FuzzerMessage(
            peer_info=PeerInfoMessage(
                fuzz_version=FUZZER_VERSION,
                features=Features(fork=FUZZER_FEATURE_FORK, ancestry=FUZZER_FEATURE_ANCESTRY),
                app_version=Version.from_str(APP_VERSION),
                jam_version=Version.from_str(GP_VERSION),
                name = "PyJAMaz"
            )
        )

    async def msg_import_block(self, req: FuzzerMessage):
        try:

            # Finalize parent TODO figure out why state root deviates when not finalizing
            self.app.state_storage.finalize(req.import_block.header.parent)

            await self.app.import_block(req.import_block)

            logging.info(f"✅ Block {format_hash(req.import_block.header.hash)} imported -> state root: {format_hash(self.app.working_state.state_root)}")
            return FuzzerMessage(state_root=self.app.working_state.state_root)

        except (StateTransitionError, BlockValidationError) as e:
            logging.info(f"🛑 Block {format_hash(req.import_block.header.hash)} raised error -> {e}")
            return FuzzerMessage(error=str(e))


    async def start(self) -> None:
        self.server = await asyncio.start_unix_server(self._handle_client, path=self.path)
        addr = self.server.sockets[0].getsockname()
        logging.info(f'🥋 PyJAMaz JAM v{APP_VERSION} [Fuzzer target v{FUZZER_VERSION}]')
        logging.info(f"🌐 Listening on {addr}")
        logging.info(f'🧾 Graypaper version: {GP_VERSION} ')

        async with self.server:
            await self.server.serve_forever()


    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        logging.info(f"[fuzzer] Accepted connection from {peer}")
        try:
            # Handshake: wait for their PeerInfo first.
            them = await FuzzerMessage.fuzzer_decode(reader)
            ours = self.msg_handshake()

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
                    rsp = await self._dispatch(req)
                except Exception as e:
                    logging.error(f"[fuzzer] Handler error for {req}: {e}")
                    break  # blunt termination on malformed/unexpected messages

                writer.write(rsp.fuzzer_encode())
                await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            logging.info("[fuzzer] Session finished")


    async def _dispatch(self, req: FuzzerMessage) -> FuzzerMessage:
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
            return self.msg_get_state()

        elif req.initialize is not None:
            return await self.msg_initialize(req)

        elif req.import_block is not None:
            return await self.msg_import_block(req)

        else:
            raise RuntimeError(f"Unknown incoming message {req.to_json()}")
