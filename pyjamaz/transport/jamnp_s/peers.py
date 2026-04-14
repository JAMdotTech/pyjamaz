from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pyjamaz.transport.jamnp_s.connection import JAMConnectionDirection

logger = logging.getLogger("pyjamaz.transport.jamnp_s")

if TYPE_CHECKING:
    from pyjamaz.transport.jamnp_s.connection import JAMConnection
    from pyjamaz.transport.jamnp_s.network import JAMNPS


class PeerRegistry:
    def __init__(self, protocol: "JAMNPS") -> None:
        self.protocol = protocol
        self.connections = {}
        self.conn_accepted = set()
        self.conn_initiated = set()
        self.conn_addr = set()


    def register(self, connection: "JAMConnection") -> None:
        self.connections[connection.jam_connection_ulid] = connection
        if connection.direction == JAMConnectionDirection.initiator:
            self.conn_initiated.add(connection.jam_connection_ulid)
        else:
            self.conn_accepted.add(connection.jam_connection_ulid)


    def activate(self, connection: "JAMConnection", addr: str) -> bool:
        if addr in self.conn_addr and connection.addr != addr:
            logger.warning(
                f"Duplicate connection from  {connection.jam_connection_ulid} direction: {connection.direction} : {addr}"
            )
            connection.close(error_code=2, reason_phrase="duplicate")
            self.unregister(connection)
            return False

        connection.addr = addr
        self.conn_addr.add(addr)

        if (
            connection.direction == JAMConnectionDirection.initiator
            and self.protocol.conn_out is None
        ):
            self.protocol.conn_out = connection

        logger.debug(
            f"Connection {connection.jam_connection_ulid} direction: {connection.direction} added {connection.addr}"
        )
        return True


    def unregister(self, connection: "JAMConnection") -> None:
        self.conn_initiated.discard(connection.jam_connection_ulid)
        self.conn_accepted.discard(connection.jam_connection_ulid)
        self.connections.pop(connection.jam_connection_ulid, None)

        if connection.addr:
            self.conn_addr.discard(connection.addr)

        if self.protocol.conn_out is connection:
            self.protocol.conn_out = next(
                (
                    conn
                    for conn in self.connections.values()
                    if conn.direction == JAMConnectionDirection.initiator and conn.addr is not None
                ),
                None,
            )
