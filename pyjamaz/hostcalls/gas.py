"""
Host function gas schedule
These helpers return upfront charges for the hostcall decorator

Graypaper 0.8.0
- B.17, page 57: G(rate, octets), the rounded size-dependent gas charge
- B.5, page 58: fetch selectors and requested-length charging
- B.6, page 61: pages modes and invokes child gas reservation
- I.4.5, pages 78-79: numeric hostfunction gas constants

"""
from pyjamaz.pvm.constants import MEM_W


def gas_cost_for_octets(rate, octets):
    """B.17: G(rate, octets) = ceil(rate * octets / 1024).

    Round the gas amount up after multiplying by the requested octet count.
    Adding 1023 (1024 - 1) implements ceiling division with integer arithmetic.
    """
    return (rate * int(octets) + 1023) // 1024


def gas_cost_by_size(base, *terms):
    """Build a base-plus-size charge using B.17 for each term separately.

    Each term is (gas per 1024 octets, register holding the requested length).
    Charge for requested lengths even if the hostcall later copies fewer bytes.
    """
    return lambda args: base + sum(gas_cost_for_octets(rate, args['registers'][reg]) for rate, reg in terms)


def gas_cost_by_item_count(base, rate, count_register):
    """Build base + rate * requested item count, without size rounding.

    count_register identifies the register holding the requested item count.

    B.7 / I.4.5: bless uses M_{B,c}=422 and M_{B,ℓ}=20 per item;
    designate uses M_{D,c}=1100 and M_{D,ℓ}=302 per validator.
    """
    return lambda args: base + rate * int(args['registers'][count_register])


# B.5 fetch (Ω_Y); values from I.4.5, page 78
# Entry i is (M_{Y,i,c}, M_{Y,i,ℓ}): (base gas, gas per 1024 requested octets)
FETCH_COSTS = (
    (390, 0),    # 0: protocol parameters
    (103, 0),    # 1: entropy
    (80, 96),    # 2: authorizer output / authorization trace
    (85, 96),    # 3: extrinsic of any work item, by index
    (85, 96),    # 4: extrinsic of the current work item, by index
    (171, 0),    # 5: imported segment of any work item, by index
    (171, 0),    # 6: imported segment of the current work item, by index
    (85, 96),    # 7: encoded work package
    (84, 0),     # 8: authorizer configuration
    (88, 0),     # 9: authorization token
    (111, 0),    # 10: refinement context
    (317, 0),    # 11: all work-item summaries
    (250, 0),    # 12: one work-item summary, by index
    (95, 96),    # 13: work-item payload, by index
    (287, 400),  # 14: all accumulation inputs
    (355, 344),  # 15: one accumulation input, by index
)


def fetch_cost(args):
    """B.5: M_{Y,c,c} + G(M_{Y,c,ℓ}, z), with selector c=r10 and size z=r9."""
    registers = args['registers']
    selector = int(registers[10])
    # B.5 defines 16 selectors (0-15). I.4.5's fallback is M_{Y,∅,c}=80,
    # M_{Y,∅,ℓ}=0 for a selector outside that range.
    base, rate = FETCH_COSTS[selector] if 0 <= selector < 16 else (80, 0)
    return base + gas_cost_for_octets(rate, registers[9])


def pages_cost(args):
    """B.6 pages (Ω_Z), page 61; constants in I.4.5, pages 78-79.

    r9 is the requested page count and r10 is the mode. Modes 0-2 clear
    contents; modes 3-4 preserve contents while changing access permissions.
    """
    registers = args['registers']
    count, mode = int(registers[9]), int(registers[10])
    if mode == 0:
        # Free/make inaccessible: M_{Z,f,c}=212, M_{Z,f,p}=118 per page.
        return 212 + 118 * count
    if mode in (1, 2):
        # Allocate read-only (1) or writable (2): M_{Z,a,c}=275, M_{Z,a,p}=121.
        return 275 + 121 * count
    if mode in (3, 4):
        # Set read-only (3) or writable (4): M_{Z,s,c}=130, M_{Z,s,p}=29.
        return 130 + 29 * count
    # Invalid mode: fixed M_{Z,i}=80, independent of the requested page count.
    return 80


def invoke_cost(args):
    """B.6 invoke (Ω_K), page 61: reserve M_K + g_R before running the child.

    I.4.5 sets M_K=968. The additional g_R is the child's requested gas budget;
    hc_invoke refunds its unused portion after execution.

    r8 points to a writable 112-byte frame: 8 bytes of little-endian gas,
    followed by 13 registers of 8 bytes each. If the frame is inaccessible,
    B.6 sets the requested budget to zero; hc_invoke handles the invalid frame.
    """
    memory, offset = args['memory'], int(args['registers'][8])
    requested = int.from_bytes(memory.read_bytes(offset, 8), 'little') if memory.is_accessible(offset, 112, MEM_W) else 0
    return 968 + requested
