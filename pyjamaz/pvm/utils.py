import numpy as np
import numpy.typing as npt

from pyjamaz.pvm.exceptions import UIntValueError


# rori -> (x >> shift_amount)∣(x << (NRBITS−shift_amount))
def rori64(x, shift_amount):
    return np.uint64(((x >> shift_amount) | (x << (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF)

def rori32(x, shift_amount):
    return np.uint32(((x >> shift_amount) | (x << (32 - shift_amount))) & 0xFFFFFFFF)

def reverse_bytes(x):
    y = 0
    y |= (x & 0x00000000000000FF) << 8 * 7
    y |= (x & 0x000000000000FF00) << 8 * 5
    y |= (x & 0x0000000000FF0000) << 8 * 3
    y |= (x & 0x00000000FF000000) << 8 * 1
    y |= (x & 0x000000FF00000000) >> 8 * 1
    y |= (x & 0x0000FF0000000000) >> 8 * 3
    y |= (x & 0x00FF000000000000) >> 8 * 5
    y |= (x & 0xFF00000000000000) >> 8 * 7
    return y

def count_trailing_zeroes(value, max_bits=64):
    #https://stackoverflow.com/a/63552117
    #https://github.com/numpy/numpy/issues/16325
    #alternative: https://gmpy2.readthedocs.io/en/latest/mpz.html
    return (value & -value).bit_length() - 1


def count_leading_zeroes(value, max_bits=64):
    #https://stackoverflow.com/a/71888844
    #https://github.com/numpy/numpy/issues/16325
    #alternative: https://gmpy2.readthedocs.io/en/latest/mpz.html
    top_bit = 1 << (max_bits - 1)
    count = 0
    value &= (1 << max_bits) - 1
    while not value & top_bit:
       count += 1
       value <<= 1
    return count


def pvm_X(x:np.uint64, n:np.uint8) -> np.uint64:
    """
    Converts number into a signed number using the MSB
    """
    x = int(x)
    n = int(n)
    # Ensure x is within the range of 2^(8*n) and never bigger than a 64 bit uint
    assert 0 <= x < 2 ** (8 * int(n)) < 2**64, "x must be in the range of 0 to 2^(8*n) - 1"

    # Calculate the term (2^64 - 2^(8*n))
    term = (2 ** 64 - 2 ** (8 * n))

    # Calculate the floor division part: floor(x / 2^(8*n - 1))
    factor = x // (2 ** (8 * n - 1))

    # Return the transformed x
    return x + factor * term


def pvm_Z(a:np.uint64, n:np.uint8) -> np.int32:
    """
    Transform number a signed a from unsigned int (max uint32) [0, 2^(8n)) to a signed int (range [-2^(8n-1), 2^(8n-1) - 1]).
    """
    a = int(a)
    n = int(n)
    boundary = 2 ** (8 * n - 1)  # This is 2^(8n-1), the boundary between positive and negative numbers.
    max_value = 2 ** (8 * n)  # This is 2^(8n), the maximum value in the n-bit space.

    # If 'a' is less than the boundary, return 'a' unchanged, otherwise subtract 2^(8n).
    if a < boundary:
        return a
    else:
        return a - max_value


def pvm_Z_inv(a:np.int64, n:np.uint8):
    """
    Transform a from the signed range [-2^(8n-1), 2^(8n-1) - 1] to unsigned range [0, 2^(8n)).
    """
    #a = int(a)
    #n = int(n)
    return ((2**(8*n)) + a) % (2**(8*n))


def read_uint(source: npt.NDArray[np.uint8], addr: np.uint32, l: np.uint8) -> np.uint32:
    if l == 1:
        return np.uint64(source[addr + 0]) % 2**8
    elif l == 2:
        byte0 = np.uint8(source[addr + 0])
        byte1 = np.uint16(source[addr + 1])
        return np.uint64((byte1 << 8) + byte0) % 2**16
    elif l == 3:
        #TODO: do 3 byte ints appear? (scale encoded maybe?)
        byte0 = np.uint8(source[addr + 0])
        byte1 = np.uint16(source[addr + 1])
        byte2 = np.uint32(source[addr + 2])
        return np.uint64((byte2 << 16) + (byte1 << 8) + byte0)  % 2**32
    elif l == 4:
        byte0 = np.uint8(source[addr + 0])
        byte1 = np.uint16(source[addr + 1])
        byte2 = np.uint32(source[addr + 2])
        byte3 = np.uint32(source[addr + 3])
        return np.uint64(
            (byte3 << 24) +
            (byte2 << 16) +
            (byte1 << 8) +
            byte0
        ) % 2**32
    elif l == 8:
        byte0 = np.uint8(source[addr + 0])
        byte1 = np.uint16(source[addr + 1])
        byte2 = np.uint32(source[addr + 2])
        byte3 = np.uint32(source[addr + 3])
        byte4 = np.uint64(source[addr + 4])
        byte5 = np.uint64(source[addr + 5])
        byte6 = np.uint64(source[addr + 6])
        byte7 = np.uint64(source[addr + 7])
        return np.uint64(
            (byte7 << 56) +
            (byte6 << 48) +
            (byte5 << 40) +
            (byte4 << 32) +
            (byte3 << 24) +
            (byte2 << 16) +
            (byte1 << 8) +
            byte0
        )

        bytes_arr = np.frombuffer(np.array([239, 190, 173, 222, 239, 190, 173, 222], dtype=np.uint8).tobytes(), dtype="<u8")[0]
    else:
        raise UIntValueError(f"Invalid uint length: {l}")


def write_uint(dest: npt.NDArray[np.uint8], addr: np.uint32, l: np.uint8, val: int):
    # Note: GP applies a modulus over the value to write denoted by their bit length
    if l < 8:
        val = val % (2 ** (l*8))

    if l == 1:
        dest[addr + 0] = np.uint8(val & 0xFF)
    elif l == 2:
        dest[addr + 0] = np.uint8( val & 0x00FF)
        dest[addr + 1] = np.uint8((val & 0xFF00) >> 8)
    elif l == 4:
        dest[addr + 0] = np.uint8( val & 0x000000FF)
        dest[addr + 1] = np.uint8((val & 0x0000FF00) >> 8)
        dest[addr + 2] = np.uint8((val & 0x00FF0000) >> 16)
        dest[addr + 3] = np.uint8((val & 0xFF000000) >> 24)
    elif l == 8:
        dest[addr + 0] = np.uint8( val & 0x00000000000000FF)
        dest[addr + 1] = np.uint8((val & 0x000000000000FF00) >> 8)
        dest[addr + 2] = np.uint8((val & 0x0000000000FF0000) >> 16)
        dest[addr + 3] = np.uint8((val & 0x00000000FF000000) >> 24)
        dest[addr + 4] = np.uint8((val & 0x000000FF00000000) >> 32)
        dest[addr + 5] = np.uint8((val & 0x0000FF0000000000) >> 40)
        dest[addr + 6] = np.uint8((val & 0x00FF000000000000) >> 48)
        dest[addr + 7] = np.uint8((val & 0xFF00000000000000) >> 56)
    else:
        raise UIntValueError(f"Invalid uint length: {l}")



# def read_i16(source: npt.NDArray[np.uint8], addr: np.uint32) -> np.int16:
#     byte0 = np.uint16(source[addr + 0])
#     byte1 = np.uint16(source[addr + 1])
#     return np.int16((byte1 << 8) + byte0)
#
#
# def read_u16(source: npt.NDArray[np.uint8], addr: np.uint32) -> np.uint16:
#     byte0 = np.uint16(source[addr + 0])
#     byte1 = np.uint16(source[addr + 1])
#     return (byte1 << 8) + byte0
#
# def read_i32(source: npt.NDArray[np.uint8], addr: np.uint32) -> np.int32:
#     byte0 = np.uint32(source[addr + 0])
#     byte1 = np.uint32(source[addr + 1])
#     byte2 = np.uint32(source[addr + 2])
#     byte3 = np.uint32(source[addr + 3])
#     return np.int32((byte3 << 24) + (byte2 << 16) + (byte1 << 8) + byte0)
#
# def read_u32(source: npt.NDArray[np.uint8], addr: np.uint32) -> np.uint32:
#     byte0 = np.uint32(source[addr + 0])
#     byte1 = np.uint32(source[addr + 1])
#     byte2 = np.uint32(source[addr + 2])
#     byte3 = np.uint32(source[addr + 3])
#     return (byte3 << 24) + (byte2 << 16) + (byte1 << 8) + byte0

# def write_i32(s, value, addr):
#     #for i in range(4): s.mem[addr + i] = (x >> (8 * i)) & 0xff
#     s.mem[addr + 0] = np.uint8(value >> (8 * 0))
#     s.mem[addr + 1] = np.uint8(value >> (8 * 1))
#     s.mem[addr + 2] = np.uint8(value >> (8 * 2))
#     s.mem[addr + 3] = np.uint8(value >> (8 * 3))

# def read_mem(s, addr):
#     mapped_addr = addr - s.mem_offset
#     #TODO: dergelijke gevallen meer generiek opvangen
#     if mapped_addr >= len(s.mem):
#         s.status = 1
#         return 0
#     return s.mem[mapped_addr]