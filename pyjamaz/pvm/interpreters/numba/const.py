NUMBA_CACHE = True


# Error codes for the JIT function
ERROR_NONE = 0
ERROR_PANIC_TRAP = 1
ERROR_PANIC_INVALID_PC = 2
ERROR_PANIC_INVALID_BRANCH = 3
ERROR_PANIC_INVALID_DJUMP = 4
ERROR_INVALID_OPCODE = 5
ERROR_MEMORY_FAULT = 6

# Memory permissions (match PVMMemoryMode enum values)
MEM_INACCESSIBLE = 0
MEM_READABLE = 1
MEM_WRITABLE = 2

# Page size constant
PVM_PAGE_SIZE = 4096
PVM_PAGE_SHIFT = 12  # 4096 = 2^12

# Exit reasons (matching ExitReason enum)
EXIT_RESUME = 0  # GP:     ▸: continue PVM
EXIT_HALT = 1  # GP-A.2: ∎: regular halt: halt
EXIT_PANIC = 2  # GP-A.2: ☇: unexpected program termination: panic
OUT_OF_GAS = 3  # GP-A.2: ∞: out-of-gas
EXIT_PAGE_FAULT = 4  # GP-A.2: F: page-fault
EXIT_HOST_HALT = 5  # GP-A.2: h: host-call


# state_out constants for invoke_jit (int64 array)
STATE_STATUS = 0
STATE_PC = 1
STATE_GAS = 2
STATE_INST_NR = 3
STATE_EXIT_VALUE = 4
STATE_SKIP_LEN = 5
STATE_ERROR = 6
STATE_CURRENT_BLOCK_START = 7
