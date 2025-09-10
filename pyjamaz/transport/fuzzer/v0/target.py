import asyncio
import logging
import os
import typing
from typing import Optional

from pyjamaz.settings import GP_VERSION, APP_VERSION
from pyjamaz.models.block import Block, Header
from pyjamaz.transport.fuzzer.v0.types import FuzzerMessage, PeerInfoMessage, Version, REQUEST_TIMEOUT
from pyjamaz.utils import format_hash

if typing.TYPE_CHECKING:
    from pyjamaz.app import PyjamazApp


def msg_handshake() -> FuzzerMessage:
    return FuzzerMessage(
        peer_info=PeerInfoMessage(
            name="PyJAMaz",
            app_version=Version.from_str(APP_VERSION),
            jam_version=Version.from_str(GP_VERSION)
        )
    )


class TargetServer:

    def __init__(self, path: str, app: 'PyjamazApp') -> None:
        self.path = path
        self.app = app

        # Wipe any stale socket first
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass
        self.server: Optional[asyncio.AbstractServer] = None


    async def start(self) -> None:
        self.server = await asyncio.start_unix_server(self._handle_client, path=self.path)
        addr = self.server.sockets[0].getsockname()
        logging.info(f'🥋 PyJAMaz JAM v{APP_VERSION} [Fuzzer target]')
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
            ours = msg_handshake()

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
            return self._msg_handshake()

        elif req.get_state is not None:

            return FuzzerMessage(
                state=list(self.app.state_db.items())
            )

        elif req.set_state is not None:

            # Flush DB
            for key, _ in self.app.state_db.items():
                self.app.state_db.delete(key)

            logging.debug(f"State DB flushed")

            # Update state from received set_state message
            for k, v in req.set_state.state:
                self.app.state_db.put(bytes(k), bytes(v))

            logging.debug(f"Privided state DB keyvals inserted")

            await self.app.initialize()
            self.app.block_context.ancestor_headers = [req.set_state.header]

            logging.info(f"💾 State set to {format_hash(self.app.state_trie_root)}")
            return FuzzerMessage(state_root=self.app.state_trie_root)

        elif req.import_block is not None:

            # Add stub parent as ancestor
            stub_parent = Header.default()
            stub_parent.hash = req.import_block.header.parent
            stub_parent.timeslot = req.import_block.header.timeslot - 1
            self.app.block_context.ancestor_headers.append(stub_parent)

            await self.app.import_block(req.import_block)
            logging.info(f"✅ Block {format_hash(req.import_block.header.hash)} imported -> state root: {format_hash(self.app.state_trie_root)}")
            return FuzzerMessage(state_root=self.app.state_trie_root)

        else:
            raise RuntimeError(f"Unknown incoming message {req.to_json()}")


    class FuzzerSession:
        def __init__(self, path: str, app: 'PyjamazApp') -> None:
            self.path = path
            self.app = app
            self.reader: asyncio.StreamReader
            self.writer: asyncio.StreamWriter

        async def connect(self) -> None:
            self.reader, self.writer = await asyncio.open_unix_connection(self.path)
            await self._do_handshake()

        async def _do_handshake(self) -> None:
            # Send our PeerInfo first
            jam_version = Version.from_str(GP_VERSION)
            our_peerinfo = msg_handshake()

            self.writer.write(our_peerinfo.fuzzer_encode())
            await self.writer.drain()

            # Await the target's PeerInfo.
            try:
                target_peerinfo = await asyncio.wait_for(FuzzerMessage.fuzzer_decode(self.reader), timeout=REQUEST_TIMEOUT)
            except asyncio.TimeoutError:
                raise RuntimeError("Target did not send PeerInfo in time")

            if target_peerinfo.peer_info.jam_version != jam_version:
                raise RuntimeError(
                    f"Protocol version mismatch: ours={GP_VERSION}, theirs={target_peerinfo.peer_info.jam_version}"
                )
            logging.info(
                f"[fuzzer] Connected to {target_peerinfo.peer_info.name} (v{target_peerinfo.peer_info.app_version})")

        async def send_request(self, req: FuzzerMessage) -> FuzzerMessage:
            """Send *req* and return the parsed response."""

            # logging.debug(f"[fuzzer] Sending {req.to_json()}")
            self.writer.write(req.fuzzer_encode())
            await self.writer.drain()
            try:
                rsp = await asyncio.wait_for(FuzzerMessage.fuzzer_decode(self.reader), timeout=REQUEST_TIMEOUT)
            except asyncio.TimeoutError:
                raise RuntimeError(f"Target timed out when responding to {req.to_json()}")
            # TODO message type sanity checks
            # logging.debug(f"[fuzzer] Received {rsp.to_json()}")
            return rsp

        async def close(self) -> None:
            self.writer.close()
            await self.writer.wait_closed()
            logging.info("[fuzzer] Session closed")
