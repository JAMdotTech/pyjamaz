from typing import Protocol

from pyjamaz.models.block import Block


class ProtocolType(Protocol):
    """Every protocol should implement these methods to be compliant"""

    async def listen(self):
        """ Starts this protocol, start listening for messages """

    #TODO: typings on data -> create dedicated Message dataclasses
    async def request_blocks(self, data):
        """ Starts a Blocks Request, to fetch a range of blocks from a given peer """

    async def broadcast_block(self, block:Block):
        """ Broadcasts a new block to all connected peers """