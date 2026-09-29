"""Graypaper 0.8, Appendix B and I.4.5 host-function gas schedule."""
from pyjamaz.pvm.constants import MEM_W


def size_cost(rate, octets):
    return (rate * int(octets) + 1023) // 1024


def sized(base, *terms):
    """Each term is (gas per KiB, register holding the requested length)."""
    return lambda args: base + sum(size_cost(rate, args['registers'][reg]) for rate, reg in terms)


def items(base, rate, register):
    return lambda args: base + rate * int(args['registers'][register])


FETCH_COSTS = (
    (390, 0), (103, 0), (80, 96), (85, 96), (85, 96), (171, 0),
    (171, 0), (85, 96), (84, 0), (88, 0), (111, 0), (317, 0),
    (250, 0), (95, 96), (287, 400), (355, 344),
)


def fetch_cost(args):
    registers = args['registers']
    selector = int(registers[10])
    base, rate = FETCH_COSTS[selector] if 0 <= selector < 16 else (80, 0)
    return base + size_cost(rate, registers[9])


def pages_cost(args):
    registers = args['registers']
    count, mode = int(registers[9]), int(registers[10])
    if mode == 0:
        return 212 + 118 * count
    if mode in (1, 2):
        return 275 + 121 * count
    if mode in (3, 4):
        return 130 + 29 * count
    return 80


def invoke_cost(args):
    memory, offset = args['memory'], int(args['registers'][8])
    requested = int.from_bytes(memory.read_bytes(offset, 8), 'little') if memory.is_accessible(offset, 112, MEM_W) else 0
    return 968 + requested
