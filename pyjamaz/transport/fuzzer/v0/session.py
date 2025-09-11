# import asyncio
# import logging
# import typing
#
# from pyjamaz.settings import GP_VERSION, APP_VERSION
# #from pyjamaz.transport.fuzzer.v0.types import FuzzerMessage, Version, PeerInfoMessage, REQUEST_TIMEOUT
# from pyjamaz.transport.fuzzer.v1.types import FuzzerMessage, Version, PeerInfoMessage, REQUEST_TIMEOUT
#
# if typing.TYPE_CHECKING:
#     from pyjamaz.app import PyjamazApp
#
#
# class FuzzerSession:
#     def __init__(self, path: str, app: 'PyjamazApp') -> None:
#         self.path = path
#         self.app = app
#         self.reader: asyncio.StreamReader
#         self.writer: asyncio.StreamWriter
#
#     def msg_handshake(self) -> FuzzerMessage:
#         return FuzzerMessage(
#             peer_info=PeerInfoMessage(
#                 name="PyJAMaz",
#                 app_version=Version.from_str(APP_VERSION),
#                 jam_version=Version.from_str(GP_VERSION)
#             )
#         )
#
#
#     async def connect(self) -> None:
#         self.reader, self.writer = await asyncio.open_unix_connection(self.path)
#         await self._do_handshake()
#
#
#     async def _do_handshake(self) -> None:
#         # Send our PeerInfo first
#         jam_version = Version.from_str(GP_VERSION)
#
#         our_peerinfo = self.msg_handshake()
#         self.writer.write(our_peerinfo.fuzzer_encode())
#         await self.writer.drain()
#
#         # Await the target's PeerInfo.
#         try:
#             target_peerinfo = await asyncio.wait_for(FuzzerMessage.fuzzer_decode(self.reader),
#                                                      timeout=REQUEST_TIMEOUT)
#         except asyncio.TimeoutError:
#             raise RuntimeError("Target did not send PeerInfo in time")
#
#         if target_peerinfo.peer_info.jam_version != jam_version:
#             raise RuntimeError(
#                 f"Protocol version mismatch: ours={GP_VERSION}, theirs={target_peerinfo.peer_info.jam_version}"
#             )
#         logging.info(
#             f"[fuzzer] Connected to {target_peerinfo.peer_info.name} (v{target_peerinfo.peer_info.app_version})")
#
#     async def send_request(self, req: FuzzerMessage) -> FuzzerMessage:
#         """Send *req* and return the parsed response."""
#
#         # logging.debug(f"[fuzzer] Sending {req.to_json()}")
#         self.writer.write(req.fuzzer_encode())
#         await self.writer.drain()
#         try:
#             rsp = await asyncio.wait_for(FuzzerMessage.fuzzer_decode(self.reader), timeout=REQUEST_TIMEOUT)
#         except asyncio.TimeoutError:
#             raise RuntimeError(f"Target timed out when responding to {req.to_json()}")
#         # TODO message type sanity checks
#         # logging.debug(f"[fuzzer] Received {rsp.to_json()}")
#         return rsp
#
#     async def close(self) -> None:
#         self.writer.close()
#         await self.writer.wait_closed()
#         logging.info("[fuzzer] Session closed")
#
