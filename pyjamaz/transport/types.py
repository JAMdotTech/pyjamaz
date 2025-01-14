from typing import Protocol


class ProtocolType(Protocol):
    """Every protocol should implement these methods to be compliant"""

    async def listen(self):
        """ Starts this protocol, start listening for messages """

    async def request_blocks(self, direction, max_blocks, block_bytes):
        """ Starts a Blocks Request, to fetch a range of blocks from a given peer """

    async def broadcast_block(self, block):
        """ Broadcasts a new block to all connected peers """