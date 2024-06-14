from scalecodec.types import Struct

from models.header import Header
from models.extrinsic import Extrinsic


class Block(Struct):
    def __init__(self):

        super().__init__(
            header=Header(),
            extrinsic=Extrinsic()
        )


class OldBlock:
    #graypaper-equation: 13
    def __init__(self, header: Header, extrinsic: Extrinsic):
        self.header = header
        self.extrinsic = extrinsic

        # graypaper-equation: 13
        # DEFINE FUNCTION THAT SERIALIZES BLOCK(DATA)

        # graypaper-equation: 13
        # DEFINE FUNCTION THAT UNSERIALIZES BLOCK(DATA)
