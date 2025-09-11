import numpy as np
import numpy.typing as npt

from pyjamaz.pvm.exceptions import PVMMemoryError

U8 = np.uint8
U16 = np.uint16
U32 = np.uint32
U64 = np.uint64
I8 = np.int8
I16 = np.int16
I32 = np.int32
I64 = np.int64


def rori64(x: U64, shift_amount: U64) -> U64:
    """JIT-compiled rotate right for 64-bit integers."""
    return U64(((x >> shift_amount) | (x << (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF)


def roli64(x: U64, shift_amount: U64) -> U64:
    """JIT-compiled rotate left for 64-bit integers."""
    return U64(((x << shift_amount) | (x >> (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF)


def rori32(x: U32, shift_amount: U32) -> U32:
    """JIT-compiled rotate right for 32-bit integers."""
    return U32(((x >> shift_amount) | (x << (32 - shift_amount))) & 0xFFFFFFFF)


def roli32(x: U32, shift_amount: U32) -> U32:
    """JIT-compiled rotate left for 32-bit integers."""
    return U32(((x << shift_amount) | (x >> (32 - shift_amount))) & 0xFFFFFFFF)


def pvm_smod(a: I64, b: I64) -> I64:
    """
    JIT-compiled signed modulo operation.

    Returns a % b with sign of a preserved.
    Special case: if b == 0, returns a.
    """
    if b == 0:
        return a

    if a >= 0:
        if b >= 0:
            return a % b
        else:
            return a % (-b)
    else:
        if b >= 0:
            return -((-a) % b)
        else:
            return -((-a) % (-b))


def pvm_rtz_div(a: I64, b: I64) -> I64:
    """
    JIT-compiled truncated division (rounds toward zero).
    """
    if a >= 0:
        if b > 0:
            return a // b
        else:
            return -(a // (-b))
    else:
        if b > 0:
            return -((-a) // b)
        else:
            return (-a) // (-b)


def pvm_X(x: U64, n: U64) -> U64:
    """JIT-compiled sign extension."""
    #TODO: cast nodig?
    #x = U64(x)
    #n = U64(n)

    if n == 1:
        masked = x & 0xFF
        if masked & 0x80:
            return U64(masked | 0xFFFFFFFFFFFFFF00)
        return U64(masked)
    elif n == 2:
        masked = x & 0xFFFF
        if masked & 0x8000:
            return U64(masked | 0xFFFFFFFFFFFF0000)
        return U64(masked)
    elif n == 3:
        masked = x & 0xFFFFFF
        if masked & 0x800000:
            return U64(masked | 0xFFFFFFFFFF000000)
        return U64(masked)
    elif n == 4:
        masked = x & 0xFFFFFFFF
        if masked & 0x80000000:
            return U64(masked | 0xFFFFFFFF00000000)
        return U64(masked)
    elif n == 5:
        masked = x & 0xFFFFFFFFFF
        if masked & 0x8000000000:
            return U64(masked | 0xFFFFFF0000000000)
        return U64(masked)
    elif n == 6:
        masked = x & 0xFFFFFFFFFFFF
        if masked & 0x800000000000:
            return U64(masked | 0xFFFF000000000000)
        return U64(masked)
    elif n == 7:
        masked = x & 0xFFFFFFFFFFFFFF
        if masked & 0x80000000000000:
            return U64(masked | 0xFF00000000000000)
        return U64(masked)
    elif n == 8:
        return U64(x & 0xFFFFFFFFFFFFFFFF)
    else:
        return U64(x)


def pvm_Z(a: U64, n: U64) -> I64:
    """JIT-friendly unsigned->signed conversion for n bytes (1..8).
    Returns I64 with proper two's-complement sign extension without Python big-ints.
    """
    au = U64(a)
    nb = U64(n)
    width = nb << U64(3)  # bits = n * 8

    # Clamp n to [1,8]; if n>=8, interpret full 64-bit as signed
    if width >= U64(64):
        return I64(au)
    if width == U64(0):
        return I64(0)

    mask = (U64(1) << width) - U64(1)
    val = au & mask
    signbit = U64(1) << (width - U64(1))

    if (val & signbit) != U64(0):
        # Negative: extend the sign bit up to 64 bits
        extend_mask = U64(0xFFFFFFFFFFFFFFFF) ^ mask
        return I64(val | extend_mask)
    else:
        # Positive
        return I64(val)


#TODO: max_bits u8 maken?
def count_leading_zeroes(value: U64, max_bits=64):
    """JIT-compiled count leading zeroes."""
    value = value & ((1 << max_bits) - 1)
    if value == 0:
        return max_bits

    count = 0
    test_bit = 1 << (max_bits - 1)

    while (value & test_bit) == 0 and count < max_bits:
        count += 1
        test_bit >>= 1

    return count


#TODO: max_bits u8 maken?
def count_trailing_zeroes(value: U64, max_bits=64):
    """JIT-compiled count trailing zeroes."""
    if value == 0:
        return max_bits

    count = 0
    temp = value
    while (temp & 1) == 0:
        count += 1
        temp >>= 1
    return count


def reverse_bytes(x: U64) -> U64:
    """JIT-compiled reverse bytes."""
    result = U64(0)
    for i in range(8):
        byte = U64((x >> U64(i * 8)) & U64(0xFF))
        result |= U64(byte << U64((7 - i) * 8))
    return result


def pvm_Z_inv(a: I64, n: U8) -> U64:
    """
    JIT-compiled transform signed to unsigned.
    """
    if n == 1:
        if a >= 0:
            return U64(a & 0xFF)
        return U64((a + (1 << 8)) & 0xFF)
    elif n == 2:
        if a >= 0:
            return U64(a & 0xFFFF)
        return U64((a + (1 << 16)) & 0xFFFF)
    elif n == 4:
        if a >= 0:
            return U64(a & 0xFFFFFFFF)
        return U64((a + I64(1 << 32)) & 0xFFFFFFFF)
    elif n == 8:
        return U64(a)
    else:
        shift = n << 3
        mask = (1 << shift) - 1
        if a >= 0:
            return U64(a & mask)
        return U64((a + (1 << shift)) & mask)


def read_uint(section: npt.NDArray[U8], addr:U32, length:U8) -> U64:
    addr32 = U32(addr)      # wrap to 32-bit address space
    len8   = U8(length)

    if len8 == U8(0):
        return U64(0)

    if len8 == U8(1):
        return U64(section[U32(addr32)])

    if len8 == U8(2):
        b0 = U64(section[U32(addr32)])
        b1 = U64(section[U32(addr32 + U32(1))])
        return b0 | (b1 << U64(8))

    if len8 == U8(3):
        b0 = U64(section[U32(addr32)])
        b1 = U64(section[U32(addr32 + U32(1))])
        b2 = U64(section[U32(addr32 + U32(2))])
        return b0 | (b1 << U64(8)) | (b2 << U64(16))

    if len8 == U8(4):
        b0 = U64(section[U32(addr32)])
        b1 = U64(section[U32(addr32 + U32(1))])
        b2 = U64(section[U32(addr32 + U32(2))])
        b3 = U64(section[U32(addr32 + U32(3))])
        return b0 | (b1 << U64(8)) | (b2 << U64(16)) | (b3 << U64(24))

    if len8 == U8(8):
        b0 = U64(section[U32(addr32 + U32(0))])
        b1 = U64(section[U32(addr32 + U32(1))])
        b2 = U64(section[U32(addr32 + U32(2))])
        b3 = U64(section[U32(addr32 + U32(3))])
        b4 = U64(section[U32(addr32 + U32(4))])
        b5 = U64(section[U32(addr32 + U32(5))])
        b6 = U64(section[U32(addr32 + U32(6))])
        b7 = U64(section[U32(addr32 + U32(7))])
        return (b0 | (b1 << U64(8))  | (b2 << U64(16)) |
                (b3 << U64(24)) | (b4 << U64(32)) |
                (b5 << U64(40)) | (b6 << U64(48)) |
                (b7 << U64(56)))

    raise Exception("read_uint: unsupported length")


def write_uint(section: npt.NDArray[U8], section_offset:U32, bytes_to_write:U8, value:U64):
    if bytes_to_write == 1:
        section[section_offset] = U8(value & 0xFF)
    elif bytes_to_write == 2:
        section[section_offset] = U8(value & 0xFF)
        section[section_offset + 1] = U8((value >> 8) & 0xFF)
    elif bytes_to_write == 4:
        section[section_offset] = U8(value & 0xFF)
        section[section_offset + 1] = U8((value >> 8) & 0xFF)
        section[section_offset + 2] = U8((value >> 16) & 0xFF)
        section[section_offset + 3] = U8((value >> 24) & 0xFF)
    elif bytes_to_write == 8:
        section[section_offset] = U8(value & 0xFF)
        section[section_offset + 1] = U8((value >> 8) & 0xFF)
        section[section_offset + 2] = U8((value >> 16) & 0xFF)
        section[section_offset + 3] = U8((value >> 24) & 0xFF)
        section[section_offset + 4] = U8((value >> 32) & 0xFF)
        section[section_offset + 5] = U8((value >> 40) & 0xFF)
        section[section_offset + 6] = U8((value >> 48) & 0xFF)
        section[section_offset + 7] = U8((value >> 56) & 0xFF)
    else:
        raise PVMMemoryError(f"Invalid write length: {bytes_to_write}")