import asyncio
import logging
import typing

from pyjamaz.settings import GP_VERSION, APP_VERSION, FUZZER_VERSION
from pyjamaz.fuzzer.v1.types import FuzzerMessage, Features, PeerInfoMessage, Version, REQUEST_TIMEOUT

if typing.TYPE_CHECKING:
    from pyjamaz.app import PyjamazApp


class FuzzerSession:
    def __init__(self, path: str, app: 'PyjamazApp') -> None:
        self.path = path
        self.app = app
        self.features = Features()
        self.reader: asyncio.StreamReader
        self.writer: asyncio.StreamWriter

    def msg_handshake(self) -> FuzzerMessage:
        return FuzzerMessage(
            peer_info=PeerInfoMessage(
                fuzz_version=FUZZER_VERSION,
                features=Features(fork=False, ancestry=False, refine=True),
                app_version=Version.from_str(APP_VERSION),
                jam_version=Version.from_str(GP_VERSION),
                name = "PyJAMaz"
            )
        )


    async def _do_handshake(self) -> None:
        # Send our PeerInfo first
        jam_version = Version.from_str(GP_VERSION)

        our_peerinfo = self.msg_handshake()
        self.writer.write(our_peerinfo.fuzzer_encode())
        await self.writer.drain()

        # Await the target's PeerInfo.
        try:
            target_peerinfo = await asyncio.wait_for(FuzzerMessage.fuzzer_decode(self.reader), timeout=REQUEST_TIMEOUT)
        except asyncio.TimeoutError:
            raise RuntimeError("Target did not send PeerInfo in time")

        if target_peerinfo.peer_info is None:
            raise RuntimeError("Target did not send PeerInfo")
        if target_peerinfo.peer_info.jam_version != jam_version:
            raise RuntimeError(
                f"Protocol version mismatch: ours={GP_VERSION}, theirs={target_peerinfo.peer_info.jam_version}"
            )

        if target_peerinfo.peer_info.fuzz_version != FUZZER_VERSION:
            raise RuntimeError(
                f"Fuzzer version mismatch: ours={FUZZER_VERSION}, theirs={target_peerinfo.peer_info.fuzz_version}"
            )

        self.features = our_peerinfo.peer_info.features & target_peerinfo.peer_info.features
        logging.info(
            f"[fuzzer] Connected to {target_peerinfo.peer_info.name} (v{target_peerinfo.peer_info.app_version})")


    async def send_request(self, req: FuzzerMessage) -> FuzzerMessage:
        """Send *req* and return the parsed response."""
        if req.refine_bundle is not None and not self.features.refine:
            raise RuntimeError("Refinement was not negotiated")
        responses = {
            'initialize': 'state_root', 'import_block': 'state_root',
            'get_state': 'state', 'refine_bundle': 'work_report',
        }
        variant = req.enum_value()[0]
        if variant not in responses:
            raise RuntimeError(f"Unexpected outgoing request {variant}")
        self.writer.write(req.fuzzer_encode())
        await self.writer.drain()
        try:
            rsp = await asyncio.wait_for(FuzzerMessage.fuzzer_decode(self.reader), timeout=REQUEST_TIMEOUT)
        except asyncio.TimeoutError:
            await self.close()
            raise RuntimeError(f"Target timed out when responding to {req.to_json()}")
        except (ValueError, asyncio.IncompleteReadError):
            await self.close()
            raise
        allowed_error = variant in ('import_block', 'refine_bundle') and rsp.error is not None
        if getattr(rsp, responses[variant]) is None and not allowed_error:
            await self.close()
            raise RuntimeError(f"Unexpected response to {variant}: expected {responses[variant]}")
        return rsp

    async def connect(self) -> None:
        self.reader, self.writer = await asyncio.open_unix_connection(self.path)
        await self._do_handshake()


    async def close(self) -> None:
        self.writer.close()
        await self.writer.wait_closed()
        logging.info("[fuzzer] Session closed")
