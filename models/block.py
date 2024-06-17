from scalecodec.types import Struct
from models.header import Header
from models.extrinsic import Extrinsic


class Block(Struct):
    #GP-equation: 13
    arguments = {
        'header': Header(),
        'extrinsic': Extrinsic(),
    }

    #GP-equation: 14 | SCALETYPE-DEFINITION: "BLOCK"->"(HEADER,EXTRINSIC)"
    #DEFINE FUNCTION THAT SERIALIZES BLOCK(DATA)
    #DEFINE FUNCTION THAT UNSERIALIZES BLOCK(DATA)
