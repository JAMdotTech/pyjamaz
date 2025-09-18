import os
import asyncio
import logging

import typing
from typing import Optional

from pyjamaz.exceptions import BlockValidationError, StateTransitionError
from pyjamaz.settings import APP_VERSION, GP_VERSION, FUZZER_VERSION
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


    async def msg_set_state(self, req) -> FuzzerMessage:
        # Flush DB
        for key, _ in self.app.state_db.as_list():
            self.app.state_db.delete(key)

        logging.debug(f"State DB flushed")

        # Update state from received set_state message
        for k, v in req.set_state.state:
            self.app.state_db.put(bytes(k), bytes(v))

        logging.debug(f"Provided state DB keyvals inserted")

        self.app.state_storage.set_finalized_header(req.set_state.header)

        await self.app.initialize(req.set_state.header)

        self.app.block_context.ancestor_headers = [req.set_state.header]

        logging.info(f"💾 State set to {format_hash(self.app.working_state.state_root)}")
        return FuzzerMessage(state_root=self.app.working_state.state_root)


    def msg_handshake(self) -> FuzzerMessage:
        return FuzzerMessage(
            peer_info=PeerInfoMessage(
                fuzz_version=FUZZER_VERSION,
                features=Features(fork=False, ancestry=False),
                app_version=Version.from_str(APP_VERSION),
                jam_version=Version.from_str(GP_VERSION),
                name = "PyJAMaz"
            )
        )

    async def msg_import_block(self, req):
        try:
            if len(self.app.block_context.ancestor_headers) == 1 and \
                self.app.block_context.ancestor_headers[0].timeslot == 0:
                # Convert stub header to valid parent
                self.app.block_context.ancestor_headers[0].timeslot = req.import_block.header.timeslot - 1
                self.app.block_context.ancestor_headers[0].hash = req.import_block.header.parent
                # Convert in state storage as well TODO merge ancestors in block_context and state_storage?
                self.app.state_storage.parents[req.import_block.header.parent] = bytes(32)

            # Finalize parent
            self.app.state_storage.finalize(req.import_block.header.parent)

            await self.app.import_block(req.import_block)

            logging.info(f"✅ Block {format_hash(req.import_block.header.hash)} imported -> state root: {format_hash(self.app.working_state.state_root)}")
            return FuzzerMessage(state_root=self.app.working_state.state_root)
        except (StateTransitionError, BlockValidationError) as e:
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

            # Main request‑response loop
            while True:
                try:
                    req = await FuzzerMessage.fuzzer_decode(reader)
                except asyncio.IncompleteReadError:
                    # EOF – fuzzer closed the connection cleanly
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

        elif req.set_state is not None:
            return await self.msg_set_state(req)

        elif req.import_block is not None:
            return await self.msg_import_block(req)

        else:
            raise RuntimeError(f"Unknown incoming message {req.to_json()}")
