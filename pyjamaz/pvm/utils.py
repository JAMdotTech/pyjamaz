from math import ceil

import numpy as np
import numpy.typing as npt

from pyjamaz.pvm.constants import PVM_PAGE_SIZE, PVM_INIT_ZONE_SIZE
from pyjamaz.pvm.exceptions import UIntValueError


# rori -> (x >> shift_amount)∣(x << (NRBITS−shift_amount))
def rori64(x, shift_amount):
    return np.uint64(((x >> shift_amount) | (x << (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF)

def roli64(x, shift_amount):
    return np.uint64(((x << shift_amount) | (x >> (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF)

def rori32(x, shift_amount):
    return np.uint32(((x >> shift_amount) | (x << (32 - shift_amount))) & 0xFFFFFFFF)

def roli32(x, shift_amount):
    return np.uint32(((x << shift_amount) | (x >> (32 - shift_amount))) & 0xFFFFFFFF)

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
    if value == 0:
        return max_bits
    return int(value & -value).bit_length() - 1


def count_leading_zeroes(value, max_bits=64):
    #https://stackoverflow.com/a/71888844
    #https://github.com/numpy/numpy/issues/16325
    #alternative: https://gmpy2.readthedocs.io/en/latest/mpz.html
    value &= (1 << max_bits) - 1  # truncate; treat negatives as 2's compliment
    if value == 0:
        return max_bits
    significant_bits = len(bin(value)) - 2  # has "0b" prefix
    return max_bits - significant_bits


def pvm_smod(a: int, b: int) -> int:
    """
    Note:
        Should be implemented / inlined using bitwise operators.
        For clarity it is as closely implemented to the definition as in the GP.
        There is a known quirk of NumPy’s type‐conversion logic on certain builds or platforms. Even though the value is below
        2**64 and should fit in uint64, NumPy internally may use a signed 64-bit conversion step first.
        Instead of np.uint64(x_int + factor*term) directly:
    """
    if b==0:
        return a
    else:
        sign_a = 1 if a >= 0 else -1
        return sign_a * (abs(a) % abs(b))


def riscv_div(x: int, y: int) -> int:
    """
    Note:
        divmod is essentially the same as integer division //, but possibly faster for large 64bit numbers:
        https://stackoverflow.com/a/30079965

        Should be implemented / inlined using bitwise operators.
        For clarity it is as closely implemented to the definition as in the GP.
        There is a known quirk of NumPy’s type‐conversion logic on certain builds or platforms. Even though the value is below
        2**64 and should fit in uint64, NumPy internally may use a signed 64-bit conversion step first.
        Instead of np.uint64(x_int + factor*term) directly:
        18446744071562035200,00000381
        18446744071562035200
    """
    x = int(x)
    y = int(y)
    q, r = divmod(x, y)
    return q


def pvm_rtz_div(a: int, b: int) -> int:
    """
    Truncates division results

    Note:
        Should be implemented / inlined using bitwise operators.
        For clarity it is as closely implemented to the definition as in the GP.
        There is a known quirk of NumPy’s type‐conversion logic on certain builds or platforms. Even though the value is below
        2**64 and should fit in uint64, NumPy internally may use a signed 64-bit conversion step first.
        Instead of np.uint64(x_int + factor*term) directly:
    """
    a = int(a)
    b = int(b)

    is_positive = (a >= 0) == (b >= 0)

    q, r = divmod(abs(a), abs(b))

    # https://math.stackexchange.com/questions/344815/how-do-the-floor-and-ceiling-functions-work-on-negative-numbers/344818#344818
    if not is_positive:
        return -q   # We take the ceil for negative numbers
    else:
        return q    # we take the floor for positive numbers


def pvm_X(x:np.uint64, n:np.uint8) -> np.uint64:
    """
    Sign extend a number to two's complement form for value X and number of bytes n

    Note:
        Should be implemented / inlined using bitwise operators.
        For clarity it is as closely implemented to the definition as in the GP.
        There is a known quirk of NumPy’s type‐conversion logic on certain builds or platforms. Even though the value is below
        2**64 and should fit in uint64, NumPy internally may use a signed 64-bit conversion step first.
    """
    x = int(x)
    n = int(n)

    assert 0 <= x < 2 ** (8 * n) <= 2**64, "x must be in the range of 0 to 2^(8*n) - 1"

    sign_mask = (2 ** 64 - 2 ** (8 * n))
    sign_bits = int(x // (2 ** (8 * n - 1)))

    return x + sign_bits * sign_mask


def pvm_Z(a:int, n:np.uint8) -> np.int64:
    """
    Transform an unsigned number into a signed number using the MSB

    Note:
        Should be implemented / inlined using bitwise operators.
        For clarity it is as closely implemented to the definition as in the GP.
        There is a known quirk of NumPy’s type‐conversion logic on certain builds or platforms. Even though the value is below
        2**64 and should fit in uint64, NumPy internally may use a signed 64-bit conversion step first.
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


def pvm_Z_inv(a:int, n:np.uint8) -> np.uint64:
    """
    Transform a signed number to an unsigned number

    Note:
        divmod is essentially the same as integer division //, but possibly faster for large 64bit numbers:
        https://stackoverflow.com/a/30079965

        Should be implemented / inlined using bitwise operators.
        For clarity it is as closely implemented to the definition as in the GP.
        There is a known quirk of NumPy’s type‐conversion logic on certain builds or platforms. Even though the value is below
        2**64 and should fit in uint64, NumPy internally may use a signed 64-bit conversion step first.
        Instead of np.uint64(x_int + factor*term) directly:
    """
    return (int(2**(8*n)) + int(a)) % int(2**(8*n))


def read_uint(source: npt.NDArray[np.uint8], addr: np.uint32, l: np.uint8) -> np.uint32:
    if l == 0:
        return 0
    elif l == 1:
        return np.uint64(source[addr + 0]) % 2**8
    elif l == 2:
        byte0 = np.uint8(source[addr + 0])
        byte1 = np.uint16(source[addr + 1])
        return np.uint64((byte1 << 8) + byte0) % 2**16
    elif l == 3:
        byte0 = np.uint8(source[addr + 0])
        byte1 = np.uint16(source[addr + 1])
        byte2 = np.uint32(source[addr + 2])
        return np.uint64((byte2 << 16) + (byte1 << 8) + byte0) % 2 ** 32
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


def page_memory(items: int) -> int:
    """
    GP-0.6.2-eq:A.38 (P)
    """
    return PVM_PAGE_SIZE * ceil(items / PVM_PAGE_SIZE)

def zone_memory(items: int) -> int:
    """
    GP-0.6.2-eq:A.38 (Z)
    """
    return PVM_INIT_ZONE_SIZE * ceil(items / PVM_INIT_ZONE_SIZE)
