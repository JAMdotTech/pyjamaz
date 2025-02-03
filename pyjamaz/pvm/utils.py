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


def pvm_floor_div(x: int, y: int) -> int:
    """
    Warning:
        The graypaper defines certain operations using a floor over a divide
        Python integer divide results in incorrect answers, same for numpy.floor_divide and true_divide
        These num,bers are represented as Floats with 53 bit integer precision, which is insufficient for some
        64bit calculations.

        For now, we fix this by casting to a 128bit precision and then truncate the result.
        Maybe look into some other options:
            https://github.com/francof2a/fxpmath
    """
    """
    Returns the quotient of x / y, truncated toward zero for positive numbers 
    without using floating-point arithmetic.
    """
    x = int(x)
    y = int(y)

    if x > 0:
        q, r = divmod(abs(x), abs(y))
        return q
    else:
        return x // y


def pvm_mod(a: int, b: int) -> int:
    # Note: Emulate C/Rust modulus (remainder) behavior using truncation toward zero
    abs_quotient = abs(a) // abs(b)
    # The sign of the quotient is positive if a and b have the same sign,
    # negative otherwise.
    quotient = abs_quotient if (a * b) >= 0 else -abs_quotient
    # Now compute the remainder
    remainder = a - quotient * b
    return remainder


def pvm_X(x:np.uint64, n:np.uint8) -> np.uint64:
    """
    Note:
    There is a known quirk of NumPy’s type‐conversion logic on certain builds or platforms. Even though the value is below 
    2**64 and should fit in uint64, NumPy internally may use a signed 64-bit conversion step first.
    Instead of np.uint64(x_int + factor*term) directly:
    """
    x = int(x)
    n = int(n)
    # Ensure x is within the range of 2^(8*n) and never bigger than a 64 bit uint
    assert 0 <= x < 2 ** (8 * int(n)) <= 2**64, "x must be in the range of 0 to 2^(8*n) - 1"

    # Calculate the term (2^64 - 2^(8*n))
    term = (2 ** 64 - 2 ** (8 * n))

    # Calculate the floor division part: floor(x / 2^(8*n - 1))
    factor = int(pvm_floor_div(np.uint64(x), np.uint64(2 ** (8 * n - 1)))) #x // (2 ** (8 * n - 1))

    # Return the transformed x
    return x + factor * term


def pvm_Z(a:int, n:np.uint8) -> np.int32:
    """
    Transform an unsigned number into a signed number using the MSB
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


def pvm_Z_inv(a:int, n:np.uint8):
    """
    Transform an signed number to an unsigned number
    """
    return (int(2**(8*n)) + int(a)) % int(2**(8*n))


def read_uint(source: npt.NDArray[np.uint8], addr: np.uint32, l: np.uint8) -> np.uint32:
    if l == 1:
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
