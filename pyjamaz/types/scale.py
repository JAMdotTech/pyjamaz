import math

from scalecodec.base import ScaleTypeDef, ScaleBytes
from scalecodec.constants import TYPE_DECOMP_MAX_RECURSIVE
from scalecodec.exceptions import ScaleEncodeException, ScaleDecodeException


class VarInt29(ScaleTypeDef):
    """
    Implementation of variable size 29 bit Integer encoding as specified in GP-0.3.2-ref:274
    """

    def decode(self, data: ScaleBytes) -> int:

        prefix = int.from_bytes(data.get_next_bytes(1), byteorder='little')

        if prefix < 128:  # Handles case for `value < 2**7`
            return prefix

        if 192 <= prefix < 224:
            length = 2
        elif 224 <= prefix < 255:
            length = 3
        else:
            length = 4

        if 1 < length < 4:  # Handles case for `2**7 <= value < 2**21`
            value_part = prefix - (2 ** 8 - 2 ** (8 - length))
            remainder = int.from_bytes(data.get_next_bytes(length - 1), byteorder='little')
            value = (prefix * 2 ** (8 * (length ))) + remainder
        elif length == 4:  # Handles case for `2**21 <= value < 2**29`
            value_part = prefix - (2 ** 8 - 2 ** 5)
            value = (value_part * 2 ** 24) + int.from_bytes(data.get_next_bytes(length - 1), byteorder='little')
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
        ScaleBytes
        """
        if value < 0:
            raise ScaleEncodeException("Cannot encode negative value")

        if value < 2**7:
            return ScaleBytes(bytes([value]))

        length = int(math.log2(value) // 7) + 1

        if 2**7 <= value < 2**21:
            prefix = (2 ** 8 - 2 ** (8 - length)) + (value // 2 ** (8 * length))
            remainder = (value % 2 ** (8 * (length - 1))).to_bytes(length - 1, byteorder='little')

        elif 2**21 <= value < 2**29:
            prefix = 2**8 - 2**5 + (value//2**24)
            remainder = (value % 2**24).to_bytes(3, byteorder='little')

        else:
            raise ScaleEncodeException("Number too large for 29-bit variable-length encoding")

        return ScaleBytes(bytes([prefix]) + remainder)

    def serialize(self, value: int) -> int:
        return value

    def deserialize(self, value: int) -> int:
        if type(value) is not int:
            raise ValueError('Value must be an integer')
        return value

    def example_value(self, _recursion_level: int = 0, max_recursion: int = TYPE_DECOMP_MAX_RECURSIVE):
        return 29


class VarInt64(ScaleTypeDef):
    """
    Implementation of variable size 64 bit Integer encoding as specified in GP-0.3.2-ref:275
    """

    def decode(self, data: ScaleBytes) -> int:

        encoded = bytes(data.data)
        prefix = encoded[0]
        remainder = encoded[1:]
        length = len(encoded)

        if length == 1:  # Handles case for `value < 2**7`
            return prefix

        elif 1 < length < 4:  # Handles case for `2**7 <= value < 2**21`
            value_part = prefix - (2 ** 8 - 2 ** (8 - length))
            value = (value_part * 2 ** (8 * (length - 1))) + int.from_bytes(remainder, byteorder='little')
        elif length == 9:  # Handles case for `2**21 <= value < 2**64`
            value_part = prefix - (2 ** 8 - 1)
            value = int.from_bytes(remainder, byteorder='little')
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

        length = int(math.log2(value) // 7) + 1

        if 2 ** 7 <= value < 2 ** 21:
            prefix = (2 ** 8 - 2 ** (8 - length)) + (value // 2 ** (8 * length))
            remainder = (value % 2 ** (8 * (length - 1))).to_bytes(length - 1, byteorder='little')

        elif 2**21 <= value < 2**64:
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
