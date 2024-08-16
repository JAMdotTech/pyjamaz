import math

from scalecodec.base import ScaleTypeDef, ScaleBytes
from scalecodec.constants import TYPE_DECOMP_MAX_RECURSIVE
from scalecodec.exceptions import ScaleEncodeException, ScaleDecodeException


class VarInt64(ScaleTypeDef):
    """
    Implementation of variable size 64bit Integer encoding as specified in GP-0.3.2-ref:275
    """

    def decode(self, data: ScaleBytes) -> int:

        prefix = int.from_bytes(data.get_next_bytes(1), byteorder='little')

        if prefix < 128:
            return prefix

        if 0x80 <= prefix < 0xc0:
            length = 1
        elif 0xc0 <= prefix < 0xe0:
            length = 2
        elif 0xe0 <= prefix < 0xf0:
            length = 3
        elif 0xf0 <= prefix < 0xf8:
            length = 4
        elif 0xf8 <= prefix < 0xfc:
            length = 5
        elif 0xfc <= prefix < 0xfe:
            length = 6
        elif 0xfe <= prefix < 0xff:
            length = 7
        else:
            length = 8

        if 1 <= length < 8:  # Handles case for `2**7 <= value < 2**21`
            value_part = prefix - (2 ** 8 - 2 ** (8 - length))
            value = (value_part * 2 ** (8 * length)) + int.from_bytes(data.get_next_bytes(length), byteorder='little')
        elif length == 8:  # Handles case for `2**21 <= value < 2**64`
            # value_part = prefix - (2 ** 8 - 1)
            value = int.from_bytes(data.get_next_bytes(8), byteorder='little')
        else:
            raise ScaleDecodeException("Unsupported length")

        return value

    def _encode(self, value: int) -> ScaleBytes:
        """
        Serializes a natural number x using a variable-length prefix with up to 4 bytes.

        Parameters
        ----------
        value

        Returns
        -------

        """
        if value < 0:
            raise ScaleEncodeException("Cannot encode negative value")

        if value < 2**7:
            return ScaleBytes(bytes([value]))

        length = math.ceil(value.bit_length() / 7) - 1

        if 2 ** 7 <= value < 2 ** 56:
            prefix = (2 ** 8 - 2 ** (8 - length)) + (value // 2 ** (8 * length))
            remainder = (value % 2 ** (8 * length)).to_bytes(length, byteorder='little')

        elif 2**56 <= value < 2**64:
            prefix = 2**8 - 1
            remainder = value.to_bytes(8, byteorder='little')

        else:
            raise ScaleEncodeException("Number too large for 64-bit variable-length encoding")

        return ScaleBytes(bytes([prefix]) + remainder)

    def serialize(self, value: int) -> int:
        return value

    def deserialize(self, value: int) -> int:
        if type(value) is not int:
            raise ValueError('Value must be an integer')
        return value

    def example_value(self, _recursion_level: int = 0, max_recursion: int = TYPE_DECOMP_MAX_RECURSIVE):
        return 64
