#!/usr/bin/env python3
"""
Test different approaches to sign extension for PVM load_i16 and similar operations
"""
import numpy as np
import timeit


# Current implementation using pvm_X
def pvm_X(x: np.uint64, n: np.uint8) -> np.uint64:
    x = int(x)
    n = int(n)

    assert 0 <= x < 2 ** (8 * n) <= 2 ** 64, "x must be in the range of 0 to 2^(8*n) - 1"

    sign_mask = (2 ** 64 - 2 ** (8 * n))
    sign_bits = int(x // (2 ** (8 * n - 1)))

    return x + sign_bits * sign_mask


# Bitwise implementation
def sign_extend_bitwise(x: int, n: int) -> int:
    # """Sign extend using bitwise operations like JavaScript"""
    # # Check if MSB is set
    sign_bit = 1 << (n * 8 - 1)
    if x & sign_bit:
        # Negative number - fill upper bits with 1s
        mask = (1 << (n * 8)) - 1
        return x | (~mask & ((1 << 64) - 1))
    else:
        # Positive number - value is already correct
        return x
    # if n == 0:
    #     # Domain contains only 0, and sign-extension of 0 bytes is 0
    #     return 0
    #
    # sign_bit = (x >> (8 * n - 1)) & 1  # 0 or 1
    # mask = sign_bit * ((1 << 64) - (1 << (8 * n)))
    # return (x & ((1 << (8 * n)) - 1)) + mask


# Numpy native signed integer conversion
def sign_extend_numpy(value: int, num_bytes: int) -> int:
    """Use NumPy's native signed integer types, return as unsigned"""
    if num_bytes == 1:
        # Mask to 8 bits first, then reinterpret as signed
        bytes_val = np.uint8(value & 0xFF).tobytes()
        signed_val = np.int64(np.frombuffer(bytes_val, dtype=np.int8)[0])
        # Convert to unsigned representation
        return int(signed_val) if signed_val >= 0 else int(signed_val) + (1 << 64)
    elif num_bytes == 2:
        # Mask to 16 bits first, then reinterpret as signed
        bytes_val = np.uint16(value & 0xFFFF).tobytes()
        signed_val = np.int64(np.frombuffer(bytes_val, dtype=np.int16)[0])
        # Convert to unsigned representation
        return int(signed_val) if signed_val >= 0 else int(signed_val) + (1 << 64)
    elif num_bytes == 3:
        # For 24-bit, we need to handle manually since there's no 24-bit type
        masked = value & 0xFFFFFF
        # Check if sign bit (bit 23) is set
        if masked & 0x800000:
            # Negative - sign extend to 64 bits
            return masked | 0xFFFFFFFFFF000000
        else:
            # Positive
            return masked
    elif num_bytes == 4:
        # Mask to 32 bits first, then reinterpret as signed
        bytes_val = np.uint32(value & 0xFFFFFFFF).tobytes()
        signed_val = np.int64(np.frombuffer(bytes_val, dtype=np.int32)[0])
        # Convert to unsigned representation
        return int(signed_val) if signed_val >= 0 else int(signed_val) + (1 << 64)
    elif num_bytes == 5:
        # For 40-bit, handle manually
        masked = value & 0xFFFFFFFFFF
        # Check if sign bit (bit 39) is set
        if masked & 0x8000000000:
            # Negative - sign extend to 64 bits
            return masked | 0xFFFFFF0000000000
        else:
            # Positive
            return masked
    elif num_bytes == 6:
        # For 48-bit, handle manually
        masked = value & 0xFFFFFFFFFFFF
        # Check if sign bit (bit 47) is set
        if masked & 0x800000000000:
            # Negative - sign extend to 64 bits
            return masked | 0xFFFF000000000000
        else:
            # Positive
            return masked
    elif num_bytes == 7:
        # For 56-bit, handle manually
        masked = value & 0xFFFFFFFFFFFFFF
        # Check if sign bit (bit 55) is set
        if masked & 0x80000000000000:
            # Negative - sign extend to 64 bits
            return masked | 0xFF00000000000000
        else:
            # Positive
            return masked
    elif num_bytes == 8:
        # For 64-bit, just return the value masked to 64 bits
        return value & 0xFFFFFFFFFFFFFFFF
    else:
        return value


# Struct-based approach
import struct


def sign_extend_struct(value: int, num_bytes: int) -> int:
    """Use struct module for sign extension, return as unsigned"""
    if num_bytes == 1:
        signed_val = struct.unpack('b', struct.pack('B', value & 0xFF))[0]
        return signed_val if signed_val >= 0 else signed_val + (1 << 64)
    elif num_bytes == 2:
        signed_val = struct.unpack('h', struct.pack('H', value & 0xFFFF))[0]
        return signed_val if signed_val >= 0 else signed_val + (1 << 64)
    elif num_bytes == 3:
        # For 24-bit, handle manually - struct doesn't have 24-bit type
        masked = value & 0xFFFFFF
        # Check if sign bit (bit 23) is set
        if masked & 0x800000:
            # Negative - sign extend to 64 bits
            return masked | 0xFFFFFFFFFF000000
        else:
            # Positive
            return masked
    elif num_bytes == 4:
        signed_val = struct.unpack('i', struct.pack('I', value & 0xFFFFFFFF))[0]
        return signed_val if signed_val >= 0 else signed_val + (1 << 64)
    elif num_bytes == 5:
        # For 40-bit, handle manually
        masked = value & 0xFFFFFFFFFF
        # Check if sign bit (bit 39) is set
        if masked & 0x8000000000:
            # Negative - sign extend to 64 bits
            return masked | 0xFFFFFF0000000000
        else:
            # Positive
            return masked
    elif num_bytes == 6:
        # For 48-bit, handle manually
        masked = value & 0xFFFFFFFFFFFF
        # Check if sign bit (bit 47) is set
        if masked & 0x800000000000:
            # Negative - sign extend to 64 bits
            return masked | 0xFFFF000000000000
        else:
            # Positive
            return masked
    elif num_bytes == 7:
        # For 56-bit, handle manually
        masked = value & 0xFFFFFFFFFFFFFF
        # Check if sign bit (bit 55) is set
        if masked & 0x80000000000000:
            # Negative - sign extend to 64 bits
            return masked | 0xFF00000000000000
        else:
            # Positive
            return masked
    elif num_bytes == 8:
        # For 64-bit, struct.unpack('q', ...) would give signed 64-bit
        # But for sign extension of 64-bit to 64-bit, just return the value
        return value & 0xFFFFFFFFFFFFFFFF
    else:
        return value


def test_correctness():
    """Test that all implementations produce the same results"""
    test_cases = [
        # (value, num_bytes, expected_signed)
        (0x7F, 1, 127),  # Positive 8-bit
        (0x80, 1, -128),  # Negative 8-bit
        (0xFF, 1, -1),  # -1 in 8-bit
        (0x7FFF, 2, 32767),  # Positive 16-bit
        (0x8000, 2, -32768),  # Negative 16-bit
        (0xFFFF, 2, -1),  # -1 in 16-bit
        (0x1234, 2, 4660),  # Random positive 16-bit
        (0xFEDC, 2, -292),  # Random negative 16-bit
        (2147483648, 4, 18446744071562067968),
        (16711681, 3, 18446744073709486081),
    ]

    print("Testing correctness...")
    for value, num_bytes, expected in test_cases:
        result1 = pvm_X(value, num_bytes)
        result2 = sign_extend_bitwise(value, num_bytes)
        result3 = sign_extend_numpy(value, num_bytes)
        result4 = sign_extend_struct(value, num_bytes)

        print(f"Value: 0x{value:08X} ({num_bytes} bytes)")
        print(f"  Expected:  {expected} (0x{expected:016X})")
        print(f"  pvm_X:     {result1} (0x{result1:016X})")
        print(f"  Bitwise:   {result2} (0x{result2:016X})")
        print(f"  NumPy:     {result3} (0x{result3:016X})")
        print(f"  Struct:    {result4} (0x{result4:016X})")

        # Check if all produce the expected result (all now return unsigned)
        assert result1 == expected, f"pvm_X failed for {value}: got {result1}, expected {expected}"
        assert result2 == expected, f"Bitwise failed for {value}: got {result2}, expected {expected}"
        assert result3 == expected, f"NumPy failed for {value}: got {result3}, expected {expected}"
        assert result4 == expected, f"Struct failed for {value}: got {result4}, expected {expected}"
        print("  ✓ All correct\n")


def benchmark():
    """Benchmark different implementations"""
    print("\nBenchmarking performance (1M iterations)...")

    # Test with 16-bit value (load_i16 case)
    test_value = 0xFEDC  # Negative 16-bit value
    num_bytes = 2
    iterations = 1_000_000

    time1 = timeit.timeit(lambda: pvm_X(test_value, num_bytes), number=iterations)
    time2 = timeit.timeit(lambda: sign_extend_bitwise(test_value, num_bytes), number=iterations)
    time3 = timeit.timeit(lambda: sign_extend_numpy(test_value, num_bytes), number=iterations)
    time4 = timeit.timeit(lambda: sign_extend_struct(test_value, num_bytes), number=iterations)

    print(f"pvm_X (current):     {time1:.3f}s")
    print(f"Bitwise:             {time2:.3f}s ({time1 / time2:.2f}x)")
    print(f"NumPy native:        {time3:.3f}s ({time1 / time3:.2f}x)")
    print(f"Struct:              {time4:.3f}s ({time1 / time4:.2f}x)")

    # Find the fastest
    times = [("pvm_X", time1), ("Bitwise", time2), ("NumPy", time3), ("Struct", time4)]
    fastest = min(times, key=lambda x: x[1])
    print(f"\nFastest: {fastest[0]}")


if __name__ == "__main__":
    test_correctness()
    benchmark()