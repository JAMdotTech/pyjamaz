from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict

from pyjamaz.transport.jamnp_s.types import JAMStreamKind

if TYPE_CHECKING:
    from pyjamaz.app import PyjamazApp
    from pyjamaz.transport.jamnp_s.peers import PeerRegistry
    from pyjamaz.transport.jamnp_s.stream_manager import StreamManager
    from pyjamaz.transport.jamnp_s.validator_manager import ValidatorConnectionManager


@dataclass
class ProtocolSharedState:
    state_requesting_blocks: bool = False
    state_warp_sync: bool = True


@dataclass
class ProtocolContext:
    app: "PyjamazApp"
    peer_registry: "PeerRegistry"
    validator_manager: "ValidatorConnectionManager"
    stream_manager: "StreamManager"
    state: ProtocolSharedState
    handlers: Dict[JAMStreamKind, object] = field(default_factory=dict)

    @property
    def connections(self):
        return self.peer_registry.connections

    @property
    def state_requesting_blocks(self) -> bool:
        return self.state.state_requesting_blocks

    @state_requesting_blocks.setter
    def state_requesting_blocks(self, value: bool) -> None:
        self.state.state_requesting_blocks = value

    @property
    def state_warp_sync(self) -> bool:
        return self.state.state_warp_sync

    @state_warp_sync.setter
    def state_warp_sync(self, value: bool) -> None:
        self.state.state_warp_sync = value

    def register_handler(self, handler) -> None:
        self.handlers[handler.kind] = handler

    def get_handler(self, kind: JAMStreamKind):
        return self.handlers[kind]
