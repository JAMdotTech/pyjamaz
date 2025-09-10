from pyjamaz.settings import APP_VERSION, GP_VERSION
from pyjamaz.transport.fuzzer.v0.target import FuzzerTarget as TargetServerV0
from pyjamaz.transport.fuzzer.v0.types import FuzzerMessage, PeerInfoMessage, Version


def _msg_handshake() -> FuzzerMessage:
    return FuzzerMessage(
        peer_info=PeerInfoMessage(
            name="PyJAMaz",
            app_version=Version.from_str(APP_VERSION),
            jam_version=Version.from_str(GP_VERSION),
        )
    )


def _handle_exception(exc):
    pass


class FuzzerTarget(TargetServerV0):

    def fuzzer_encode(self) -> bytes:
        pass

    @classmethod
    async def fuzzer_decode(cls, reader: asyncio.StreamReader) -> "FuzzerMessage":
        pass