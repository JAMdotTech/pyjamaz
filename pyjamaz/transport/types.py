from typing import Protocol

from pyjamaz.models.block import Block
from pyjamaz.models.common import ValidatorData, WorkPackageSpec


class ProtocolType(Protocol):
    """Every protocol should implement these methods to be compliant"""

    async def listen(self):
        """ Starts this protocol, start listening for messages """

    async def request_blocks(self, direction: int, max_blocks: int, block_bytes:bytes):
        """ Starts a Blocks Request, to fetch a range of blocks from a given peer """

    async def broadcast_block(self, block:Block):
        """ Broadcasts a new block to all connected peers """

    async def request(self, peer: ValidatorData, kind: int, messages: list[bytes]) -> list[bytes]:
        """Exchange framed messages on an authenticated JAMNP-S CE stream."""

    async def request_validator_shard(self, peer: ValidatorData, spec: WorkPackageSpec, shard_index: int):
        """Retrieve and verify a complete CE137 validator row."""

    async def request_segment_shards(self, peer: ValidatorData, spec: WorkPackageSpec,
                                     shard_index: int, segment_indices, *, proven=False):
        """Retrieve CE139 chunks or individually verified CE140 chunks."""

    async def request_segments(self, peer: ValidatorData, root: bytes, indices):
        """Retrieve complete CE148 segments and verify their import proofs."""
