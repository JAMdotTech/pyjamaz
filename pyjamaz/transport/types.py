from typing import Protocol

from pyjamaz.models.block import Block


class ProtocolType(Protocol):
    """Every protocol should implement these methods to be compliant"""

    async def listen(self):
        """ Starts this protocol, start listening for messages """
