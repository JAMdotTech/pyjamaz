import numpy as np

from pyjamaz.pvm.exceptions import UIntValueError

# Type definitions

def u8(x: int) -> np.uint8:
    return np.uint8(x)

def i8(x: int) -> np.int8:
    return np.int8(x)

def u16(x: int) -> np.uint16:
    return np.uint16(x)

def i16(x: int) -> np.int16:
    return np.int16(x)

def u32(x: int) -> np.uint32:
    return np.uint32(x)

def i32(x: int) -> np.int32:
    return np.int32(x)

def u64(x: int) -> np.uint64:
    return np.uint64(x)

def i64(x: int) -> np.int64:
    return np.int64(x)


# Pvm helper functions:

def rori64(x, shift_amount) -> np.uint64:
    shift_amount = int(shift_amount) & 63
    return np.uint64(((x >> shift_amount) | (x << (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF)


def roli64(x, shift_amount) -> np.uint64:
    shift_amount = int(shift_amount) & 63
    return np.uint64(((x << shift_amount) | (x >> (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF)


def rori32(x, shift_amount) -> np.uint32:
    shift_amount = int(shift_amount) & 31
    return np.uint32(((x >> shift_amount) | (x << (32 - shift_amount))) & 0xFFFFFFFF)


def roli32(x, shift_amount) -> np.uint32:
    shift_amount = int(shift_amount) & 31
    return np.uint32(((x << shift_amount) | (x >> (32 - shift_amount))) & 0xFFFFFFFF)


def reverse_bytes(x) -> int:
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


def count_trailing_zeroes(value, max_bits=64) -> int:
    # https://stackoverflow.com/a/63552117
    # https://github.com/numpy/numpy/issues/16325
    # alternative: https://gmpy2.readthedocs.io/en/latest/mpz.html
    if value == 0:
        return max_bits
    return int(value & -value).bit_length() - 1


def count_leading_zeroes(value, max_bits=64) -> int:
    # https://stackoverflow.com/a/71888844
    # https://github.com/numpy/numpy/issues/16325
    # alternative: https://gmpy2.readthedocs.io/en/latest/mpz.html
    value &= (1 << max_bits) - 1  # truncate; treat negatives as 2's compliment
    if value == 0:
        return max_bits
    significant_bits = len(bin(value)) - 2  # has "0b" prefix
    return max_bits - significant_bits


def pvm_smod(a: int, b: int) -> int:
    if b==0:
        return a
    else:
        sign_a = 1 if a >= 0 else -1
        return sign_a * (abs(a) % abs(b))


def pvm_rtz_div(a: int, b: int) -> int:
    a = int(a)
    b = int(b)

    is_positive = (a >= 0) == (b >= 0)

    q, r = divmod(abs(a), abs(b))

    # https://math.stackexchange.com/questions/344815/how-do-the-floor-and-ceiling-functions-work-on-negative-numbers/344818#344818
    if not is_positive:
        return -q   # We take the ceil for negative numbers
    else:
        return q    # we take the floor for positive numbers


def pvm_X(x: int, n: int) -> int:
    x = int(x)
    n = int(n)

    assert 0 <= x < 2 ** (8 * n) <= 2**64, "x must be in the range of 0 to 2^(8*n) - 1"

    sign_mask = (2 ** 64 - 2 ** (8 * n))
    sign_bits = int(x // (2 ** (8 * n - 1)))

    return x + sign_bits * sign_mask


def pvm_Z(a: int, n: int) -> int:
    a = int(a)
    n = int(n)
    boundary = 2 ** (8 * n - 1)  # This is 2^(8n-1), the boundary between positive and negative numbers.
    max_value = 2 ** (8 * n)  # This is 2^(8n), the maximum value in the n-bit space.

    # If 'a' is less than the boundary, return 'a' unchanged, otherwise subtract 2^(8n).
    if a < boundary:
        return a
    else:
        return a - max_value


def pvm_Z_inv(a: int, n: int) -> int:
    return (int(2**(8*n)) + int(a)) % int(2**(8*n))


def read_uint(source: bytearray, addr: np.uint32, l: np.uint8) -> np.uint64:
    if l == 0:
        return u64(0)
    elif l == 1:
        return u64(source[addr + 0]) % 2**8
    elif l == 2:
        byte0 = u8(source[addr + 0])
        byte1 = u16(source[addr + 1])
        return u64((byte1 << 8) + byte0) % 2**16
    elif l == 3:
        byte0 = u8(source[addr + 0])
        byte1 = u16(source[addr + 1])
        byte2 = u32(source[addr + 2])
        return u64((byte2 << 16) + (byte1 << 8) + byte0) % 2 ** 32
    elif l == 4:
        byte0 = u8(source[addr + 0])
        byte1 = u16(source[addr + 1])
        byte2 = u32(source[addr + 2])
        byte3 = u32(source[addr + 3])
        return u64(
            (byte3 << 24) +
            (byte2 << 16) +
            (byte1 << 8) +
            byte0
        ) % 2**32
    elif l == 8:
        byte0 = u8(source[addr + 0])
        byte1 = u16(source[addr + 1])
        byte2 = u32(source[addr + 2])
        byte3 = u32(source[addr + 3])
        byte4 = u64(source[addr + 4])
        byte5 = u64(source[addr + 5])
        byte6 = u64(source[addr + 6])
        byte7 = u64(source[addr + 7])
        return u64(
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
