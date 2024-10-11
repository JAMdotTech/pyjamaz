#import numpy as np
#import numpy.typing as npt
import np
#import npt

#from pyjamaz.pvm.exceptions import UIntValueError


#gp_0.3.6_eq_223
def pvm_X(x:np.uint32, n:np.uint8) -> np.uint32:
    """
    Converts number into a signed number using the MSB
    """
    x = int(x)
    n = int(n)
    # Ensure x is within the range of 2^(8*n)
    assert 0 <= x < 2 ** (8 * int(n)), "x must be in the range of 0 to 2^(8*n) - 1"

    # Calculate the term (2^32 - 2^(8*n))
    term = (2 ** 32 - 2 ** (8 * n))

    # Calculate the floor division part: floor(x / 2^(8*n - 1))
    factor = x // (2 ** (8 * n - 1))

    # Return the transformed x
    return x + factor * term


def pvm_Zn(a:np.uint32, n:np.uint8) -> np.int32:
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


def pvm_Zn_inv(a:np.int32, n:np.uint8):
    """
    Transform a from the signed range [-2^(8n-1), 2^(8n-1) - 1] to unsigned range [0, 2^(8n)).
    """
    #a = int(a)
    #n = int(n)
    return ((2**(8*n)) + a) % (2**(8*n))


# def pvm_Bn(x, n):
#     """
#     Transforms an integer x from the range [0, 2^(8n)) into a bit array y of length 8n.
#     """
#     # Ensure x is within the valid range
#     max_value = 2 ** (8 * n)
#     if not (0 <= x < max_value):
#         raise ValueError(f"x must be in the range [0, {max_value - 1}] for the given n={n}")
#
#     # Initialize the bit array y with zeros
#     bit_array = np.zeros(8 * n, dtype=int)
#
#     # Fill the bit array using the formula y[i] = (x // (2^i)) % 2
#     for i in range(8 * n):
#         bit_array[i] = (x // (2 ** i)) % 2
#
#     return bit_array

def read_uint(source, addr: np.uint32, l: np.uint8) -> np.uint32:
    if l == 1:
        return np.uint32(source[addr + 0])
    elif l == 2:
        byte0 = np.uint8(source[addr + 0])
        byte1 = np.uint16(source[addr + 1])
        return np.uint32((byte1 << 8) + byte0)
    elif l == 3:
        byte0 = np.uint8(source[addr + 0])
        byte1 = np.uint16(source[addr + 1])
        byte2 = np.uint32(source[addr + 2])
        return np.uint32((byte2 << 16) + (byte1 << 8) + byte0)
    elif l == 4:
        byte0 = np.uint8(source[addr + 0])
        byte1 = np.uint16(source[addr + 1])
        byte2 = np.uint32(source[addr + 2])
        byte3 = np.uint32(source[addr + 3])
        return np.uint32((byte3 << 24) + (byte2 << 16) + (byte1 << 8) + byte0)
    else:
        raise Exception(f"Invalid uint length: {l}")


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