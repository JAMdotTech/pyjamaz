#gp_0.3.6_eq_223
# def sign_extend(x,n):
#     term = (2 ** 32 - 2 ** (8 * n))
#     factor = x // (2 ** (8 * n - 1))
#     return x + factor * term
def pvm_X(x, n):
    # TODO: cast naar python int -> port naar numpy
    n = int(n)
    # Ensure x is within the range of 2^(8*n)
    assert 0 <= x < 2 ** (8 * int(n)), "x must be in the range of 0 to 2^(8*n) - 1"

    # Calculate the term (2^32 - 2^(8*n))
    term = (2 ** 32 - 2 ** (8 * n))

    # Calculate the floor division part: floor(x / 2^(8*n - 1))
    factor = x // (2 ** (8 * n - 1))

    # Return the transformed x
    return x + factor * term


def pvm_Zn(a, n):
    """
    Transform a from the range [0, 2^(8n)) to the signed range [-2^(8n-1), 2^(8n-1) - 1].
    """
    # TODO: cast naar python int -> port naar numpy
    a = int(a)
    n = int(n)

    boundary = 2 ** (8 * n - 1)  # This is 2^(8n-1), the boundary between positive and negative numbers.
    max_value = 2 ** (8 * n)-1  # This is 2^(8n), the maximum value in the n-bit space.

    # If 'a' is less than the boundary, return 'a' unchanged, otherwise subtract 2^(8n).
    if a < boundary:
        return a
    else:
        return a - max_value

def pvm_Zn_inv(a, n):
    """
    Transform a from the range [0, 2^(8n)) to the signed range [-2^(8n-1), 2^(8n-1) - 1].
    """
    # TODO: cast naar python int -> port naar numpy
    return ((2**(8*n)) + a) % (2**(8*n))
