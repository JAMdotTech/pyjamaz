import numpy as np
import numpy.typing as npt

from numba import njit, types
from numba import uint8, uint32, int32, uint64, int64, boolean

from pyjamaz.pvm.numba.const import NUMBA_CACHE, PVM_PAGE_SHIFT

U8 = np.uint8
U16 = np.uint16
U32 = np.uint32
U64 = np.uint64
I8 = np.int8
I16 = np.int16
I32 = np.int32
I64 = np.int64


U64_MASK = U64(0xFFFFFFFFFFFFFFFF)
U32_MASK = U64(0xFFFFFFFF)

u8_array_1d = types.Array(uint8, 1, 'C')
u8_array_list = types.ListType(u8_array_1d)
u64_array_1d = types.Array(uint64, 1, 'C')
u64_array_list = types.ListType(u64_array_1d)
int32_array_1d = types.Array(int32, 1, 'C')


ACL_PAGES_PER_BITMAP = 32
ACL_BITS_PER_PAGE = 2
ACL_READ_BIT = np.uint64(0b01)
ACL_WRITE_BIT = np.uint64(0b10)


@njit(uint64(uint64[::1], int32), cache=NUMBA_CACHE)
def acl_bits_for_page(acl_bitmap, page_idx: I32) -> U64:
    if page_idx < 0:
        return U64(0)
    if len(acl_bitmap) == 0:
        return U64(0b11)

    bitmap_idx = page_idx // ACL_PAGES_PER_BITMAP
    if bitmap_idx >= len(acl_bitmap):
        return U64(0)

    pos = page_idx % ACL_PAGES_PER_BITMAP
    shift = (ACL_PAGES_PER_BITMAP - 1 - pos) * ACL_BITS_PER_PAGE
    return (acl_bitmap[bitmap_idx] >> U64(shift)) & U64(0b11)


@njit(types.UniTuple(uint64, 2)(uint64, uint64), cache=NUMBA_CACHE)
def umul64wide_jit(a: U64, b: U64) -> (U64, U64):
    """Unsigned 64x64 -> (hi, lo) as uint64s."""
    mask32 = U64(0xFFFFFFFF)
    a_lo = a & mask32
    a_hi = a >> U64(32)
    b_lo = b & mask32
    b_hi = b >> U64(32)

    ll = a_lo * b_lo  # 64-bit
    lh = a_lo * b_hi
    hl = a_hi * b_lo
    hh = a_hi * b_hi

    carry = (ll >> U64(32)) + (lh & mask32) + (hl & mask32)
    lo = (ll & mask32) | ((carry & mask32) << U64(32))
    hi = hh + (lh >> U64(32)) + (hl >> U64(32)) + (carry >> U64(32))
    return U64(hi), U64(lo)


@njit(types.UniTuple(uint64, 2)(int64, int64), cache=NUMBA_CACHE)
def imul64wide_jit(a: I64, b: I64) -> (U64, U64):
    """Signed 64x64 -> (hi, lo) representing 128-bit two's-complement product."""
    ua = U64(a)  # reinterpret
    ub = U64(b)
    hi, lo = umul64wide_jit(ua, ub)
    # Adjust high word for two's-complement signs (see Hacker's Delight)
    if a < 0:
        hi = U64(hi - ub)
    if b < 0:
        hi = U64(hi - ua)
    return U64(hi), U64(lo)


@njit(types.UniTuple(uint64, 2)(int64, uint64), cache=NUMBA_CACHE)
def smul_u64wide_jit(a: I64, b: U64) -> (U64, U64):
    """Signed * Unsigned -> (hi, lo), two's-complement."""
    ua = U64(a)
    hi, lo = umul64wide_jit(ua, b)
    if a < 0:
        hi = U64(hi - b)
    return U64(hi), U64(lo)


@njit(uint64(uint64, uint64), cache=NUMBA_CACHE)
def rori64_jit(x: U64, shift_amount: U64) -> U64:
    """Rotate right for 64-bit integers."""
    return U64(((x >> shift_amount) | (x << (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF)


@njit(uint64(uint64, uint64), cache=NUMBA_CACHE)
def roli64_jit(x: U64, shift_amount: U64) -> U64:
    """Rotate left for 64-bit integers."""
    return U64(((x << shift_amount) | (x >> (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF)


@njit(uint32(uint32, uint32), cache=NUMBA_CACHE)
def rori32_jit(x: U32, shift_amount: U32) -> U32:
    """Rotate right for 32-bit integers."""
    return U32(((x >> shift_amount) | (x << (32 - shift_amount))) & 0xFFFFFFFF)


@njit(uint32(uint32, uint32), cache=NUMBA_CACHE)
def roli32_jit(x: U32, shift_amount: U32) -> U32:
    """Rotate left for 32-bit integers."""
    return U32(((x << shift_amount) | (x >> (32 - shift_amount))) & 0xFFFFFFFF)


@njit(int64(int64, int64), cache=NUMBA_CACHE)
def pvm_smod_jit(a: I64, b: I64) -> I64:
    """
    Signed modulo operation.
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


@njit(int64(int64, int64), cache=NUMBA_CACHE)
def pvm_rtz_div_jit(a: I64, b: I64) -> I64:
    """
    Truncated division (rounds toward zero).
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


@njit(uint64(uint64, uint64), cache=NUMBA_CACHE)
def pvm_X_jit(x: U64, n: U64) -> U64:
    # TODO: remove cast
    x = U64(x)
    n = U64(n)

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


@njit(int64(uint64, uint64), cache=NUMBA_CACHE)
def pvm_Z_jit(a: U64, n: U64) -> I64:
    """
    Unsigned->signed conversion for n bytes (1..8).
    Returns I64 with proper two's-complement sign extension without Python big-ints.
    """
    #TODO: remove casts
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


@njit(uint64(uint64, uint8), cache=NUMBA_CACHE)
def count_leading_zeroes_jit(value: U64, max_bits:U8) -> U64:
    """
    Count-leading-zeroes with explicit 64-bit masking and shifts.
    Matches Python implementation for max_bits in {32,64}.
    """
    mb = U64(max_bits)
    # Build mask and starting test bit using 64-bit arithmetic
    if mb >= U64(64):
        mask = U64(0xFFFFFFFFFFFFFFFF)
        test_bit = U64(1) << U64(63)
        maxb = 64
    else:
        mask = (U64(1) << mb) - U64(1)
        test_bit = U64(1) << (mb - U64(1))
        maxb = int(mb)

    val = U64(value) & mask
    if val == U64(0):
        return maxb

    count = 0
    while (val & test_bit) == U64(0) and count < maxb:
        count += 1
        test_bit = test_bit >> U64(1)

    return count


@njit(uint64(uint64, uint8), cache=NUMBA_CACHE)
def count_trailing_zeroes_jit(value: U64, max_bits: U8) -> U64:
    #TODO: optimize?
    if value == 0:
        return max_bits

    count = 0
    temp = value
    while (temp & 1) == 0:
        count += 1
        temp >>= 1
    return count


@njit(uint64(uint64), cache=NUMBA_CACHE)
def reverse_bytes_jit(x: U64) -> U64:
    #TODO: optimize?
    result = U64(0)
    for i in range(8):
        byte = U64((x >> U64(i * 8)) & U64(0xFF))
        result |= U64(byte << U64((7 - i) * 8))
    return result


@njit(int64(int64, int64), cache=NUMBA_CACHE)
def riscv_div_jit(a: I64, b: I64) -> I64:
    if b == 0:
        return I64(-1)
    return a // b


@njit(uint64(int64, uint8), cache=NUMBA_CACHE)
def pvm_Z_inv_jit(a: I64, n: U8) -> U64:
    """
    Signed to unsigned.
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


@njit(uint64(uint8[::1], uint32, uint8), cache=NUMBA_CACHE)
def read_uint_jit(code: npt.NDArray[U8], addr: U32, length: U8) -> U64:
    addr32 = U32(addr)  # wrap to 32-bit address space
    len8 = U8(length)

    if len8 == U8(0):
        return U64(0)

    if len8 == U8(1):
        return U64(code[U32(addr32)])

    if len8 == U8(2):
        b0 = U64(code[U32(addr32)])
        b1 = U64(code[U32(addr32 + U32(1))])
        return b0 | (b1 << U64(8))

    if len8 == U8(3):
        b0 = U64(code[U32(addr32)])
        b1 = U64(code[U32(addr32 + U32(1))])
        b2 = U64(code[U32(addr32 + U32(2))])
        return b0 | (b1 << U64(8)) | (b2 << U64(16))

    if len8 == U8(4):
        b0 = U64(code[U32(addr32)])
        b1 = U64(code[U32(addr32 + U32(1))])
        b2 = U64(code[U32(addr32 + U32(2))])
        b3 = U64(code[U32(addr32 + U32(3))])
        return b0 | (b1 << U64(8)) | (b2 << U64(16)) | (b3 << U64(24))

    if len8 == U8(8):
        b0 = U64(code[U32(addr32 + U32(0))])
        b1 = U64(code[U32(addr32 + U32(1))])
        b2 = U64(code[U32(addr32 + U32(2))])
        b3 = U64(code[U32(addr32 + U32(3))])
        b4 = U64(code[U32(addr32 + U32(4))])
        b5 = U64(code[U32(addr32 + U32(5))])
        b6 = U64(code[U32(addr32 + U32(6))])
        b7 = U64(code[U32(addr32 + U32(7))])
        return (b0 | (b1 << U64(8)) | (b2 << U64(16)) |
                (b3 << U64(24)) | (b4 << U64(32)) |
                (b5 << U64(40)) | (b6 << U64(48)) |
                (b7 << U64(56)))

    raise Exception("read_uint: unsupported length")


@njit(int32(
    uint64,        # addr
    uint64,        # value
    uint8,         # bytes_to_write
    uint64[::1],   # section_starts
    uint64[::1],   # section_ends
    u8_array_list, # section_arrays
    u64_array_list,# acl_bitmaps
    int32[::1],    # acl_extra_start
    int32[::1]     # acl_extra_count
), cache=NUMBA_CACHE)
def mem_write_jit(addr: U64, value: U64, bytes_to_write: U8,
                  section_starts, section_ends, section_arrays,
                  acl_bitmaps, acl_extra_start, acl_extra_count) -> I32:
    """
    Returns status:I32 where status==0 on success, -1 on fault.
    """
    idx = I32(-1)
    for i in range(len(section_starts)):
        if section_starts[i] <= addr <= section_ends[i]:
            idx = I32(i)
            break
    if idx < 0:
        return I32(-1)

    start = U64(section_starts[idx])
    off = addr - start

    # start_page_rel = 0
    # end_page_rel = -1
    # if bytes_to_write > U8(0):
    #     start_page_rel = int(off >> PVM_PAGE_SHIFT)
    #     end_page_rel = int(((off + U64(bytes_to_write) - U64(1)) >> PVM_PAGE_SHIFT))
    #
    # allowed = True
    # section_acl = acl_bitmaps[idx]
    # if len(section_acl) > 0 and bytes_to_write > U8(0):
    #     required = ACL_READ_BIT | ACL_WRITE_BIT
    #     for page_rel in range(start_page_rel, end_page_rel + 1):
    #         bits = acl_bits_for_page(section_acl, page_rel)
    #         if (bits & required) != required:
    #             allowed = False
    #             break
    #
    # if not allowed:
    #     base_page_abs = int(section_starts[idx] >> PVM_PAGE_SHIFT)
    #     start_page_abs = base_page_abs + start_page_rel
    #     end_page_abs = base_page_abs + end_page_rel
    #     extra_start = int(acl_extra_start[0])
    #     extra_count = int(acl_extra_count[0])
    #     if extra_count > 0:
    #         extra_end = extra_start + extra_count
    #         if start_page_abs >= extra_start and end_page_abs < extra_end:
    #             allowed = True
    #
    # if not allowed:
    #     return I32(-1)

    a = section_arrays[idx]  # uint8[::1]
    if off + U64(bytes_to_write) > U64(len(a)):
        return I32(-1)

    # Mask value for <8 byte writes
    if bytes_to_write < U8(8):
        shift = U64(bytes_to_write) * U64(8)
        mask = (U64(1) << shift) - U64(1)
        value = value & mask

    base = int(off)

    if bytes_to_write == U8(1):
        a[base] = U8(value & U64(0xFF))
    elif bytes_to_write == U8(2):
        a[base] = U8(value & U64(0xFF))
        a[base + 1] = U8((value >> U64(8)) & U64(0xFF))
    elif bytes_to_write == U8(4):
        a[base] = U8(value & U64(0xFF))
        a[base + 1] = U8((value >> U64(8)) & U64(0xFF))
        a[base + 2] = U8((value >> U64(16)) & U64(0xFF))
        a[base + 3] = U8((value >> U64(24)) & U64(0xFF))
    elif bytes_to_write == U8(8):
        a[base] = U8(value & U64(0xFF))
        a[base + 1] = U8((value >> U64(8)) & U64(0xFF))
        a[base + 2] = U8((value >> U64(16)) & U64(0xFF))
        a[base + 3] = U8((value >> U64(24)) & U64(0xFF))
        a[base + 4] = U8((value >> U64(32)) & U64(0xFF))
        a[base + 5] = U8((value >> U64(40)) & U64(0xFF))
        a[base + 6] = U8((value >> U64(48)) & U64(0xFF))
        a[base + 7] = U8((value >> U64(56)) & U64(0xFF))
    else:
        return I32(-1)

    return I32(0)


@njit(types.Tuple((int32, uint64))(
    uint64,        # addr
    uint8,         # bytes_to_read
    uint64[::1],   # section_starts
    uint64[::1],   # section_ends
    u8_array_list, # section_arrays
    u64_array_list,# acl_bitmaps
    int32[::1],    # acl_extra_start
    int32[::1]     # acl_extra_count
), cache=NUMBA_CACHE)
def mem_read_jit(addr: U64, bytes_to_read: U8,
                 section_starts, section_ends, section_arrays,
                 acl_bitmaps, acl_extra_start, acl_extra_count) -> (I32, U64):
    """
    Returns (status:I32, value:U64) where status==0 on success, -1 on fault.
    """
    idx = I32(-1)
    for i in range(len(section_starts)):
        if section_starts[i] <= addr <= section_ends[i]:
            idx = I32(i)
            break
    if idx < 0:
        return I32(-1), U64(0)

    start = U64(section_starts[idx])
    off = addr - start

    # start_page_rel = 0
    # end_page_rel = -1
    # if bytes_to_read > U8(0):
    #     start_page_rel = int(off >> PVM_PAGE_SHIFT)
    #     end_page_rel = int(((off + U64(bytes_to_read) - U64(1)) >> PVM_PAGE_SHIFT))

    # allowed = True
    # section_acl = acl_bitmaps[idx]
    # if len(section_acl) > 0 and bytes_to_read > U8(0):
    #     required = ACL_READ_BIT
    #     for page_rel in range(start_page_rel, end_page_rel + 1):
    #         bits = acl_bits_for_page(section_acl, page_rel)
    #         if (bits & required) != required:
    #             allowed = False
    #             break
    #
    # if not allowed:
    #     base_page_abs = int(section_starts[idx] >> PVM_PAGE_SHIFT)
    #     start_page_abs = base_page_abs + start_page_rel
    #     end_page_abs = base_page_abs + end_page_rel
    #     extra_start = int(acl_extra_start[0])
    #     extra_count = int(acl_extra_count[0])
    #     if extra_count > 0:
    #         extra_end = extra_start + extra_count
    #         if start_page_abs >= extra_start and end_page_abs < extra_end:
    #             allowed = True
    #
    # if not allowed:
    #     return I32(-1), U64(0)

    a = section_arrays[idx]  # uint8[::1] array
    if off + U64(bytes_to_read) > U64(len(a)):
        return I32(-1), U64(0)
    base = int(off)

    if bytes_to_read == U8(1):
        return I32(0), U64(a[base])
    elif bytes_to_read == U8(2):
        return I32(0), (U64(a[base]) | (U64(a[base + 1]) << U64(8)))
    elif bytes_to_read == U8(4):
        return I32(0), (U64(a[base]) |
                        (U64(a[base + 1]) << U64(8)) |
                        (U64(a[base + 2]) << U64(16)) |
                        (U64(a[base + 3]) << U64(24)))
    elif bytes_to_read == U8(8):
        return I32(0), (U64(a[base]) |
                        (U64(a[base + 1]) << U64(8)) |
                        (U64(a[base + 2]) << U64(16)) |
                        (U64(a[base + 3]) << U64(24)) |
                        (U64(a[base + 4]) << U64(32)) |
                        (U64(a[base + 5]) << U64(40)) |
                        (U64(a[base + 6]) << U64(48)) |
                        (U64(a[base + 7]) << U64(56)))
    else:
        return I32(-1), U64(0)
