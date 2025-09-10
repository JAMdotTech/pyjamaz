import asyncio
import logging
import typing

from pyjamaz.settings import GP_VERSION, APP_VERSION
from pyjamaz.transport.fuzzer.v0.types import FuzzerMessage, Version, PeerInfoMessage, REQUEST_TIMEOUT

if typing.TYPE_CHECKING:
    from pyjamaz.app import PyjamazApp


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

        our_peerinfo = FuzzerMessage(
            peer_info=PeerInfoMessage(
                name="PyJAMaz",
                app_version=Version.from_str(APP_VERSION),
                jam_version=jam_version
            )
        )
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
        logging.info(f"[fuzzer] Connected to {target_peerinfo.peer_info.name} (v{target_peerinfo.peer_info.app_version})")