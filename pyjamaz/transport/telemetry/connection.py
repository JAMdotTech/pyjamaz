"""Network connection helper for telemetry client."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("pyjamaz.transport.telemetry")


class TelemetryConnectionError(Exception):
    """Oopsie! Raised when telemetry connection fail"""


class TelemetryConnection:
    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._lock = asyncio.Lock()

    def is_connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    async def connect(self) -> None:
        logger.debug("Connecting telemetry to %s:%s", self._host, self._port)
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
        logger.info("Telemetry connected to %s:%s", self._host, self._port)

    async def send(self, data: bytes) -> None:
        if not self.is_connected():
            raise TelemetryConnectionError("Telemetry connection is not available")

        async with self._lock:
            assert self._writer is not None
            self._writer.write(data)
            await self._writer.drain()

    async def close(self) -> None:
        if self._writer:
            logger.info("Closing telemetry connection to %s:%s", self._host, self._port)
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except AttributeError:
                await asyncio.sleep(0)
            except (ConnectionResetError, BrokenPipeError):
                logger.debug("Telemetry connection already closed by peer")
            except RuntimeError as exc:
                logger.debug("Telemetry wait_closed runtime error: %s", exc)

        self._reader = None
        self._writer = None
