from pvm.exceptions import InvalidOpcode, PanicError


def _op_invalid(vm):
    raise InvalidOpcode(f"Invalid opcode: {vm.opcode}")

def _op_trap(vm):
    vm.log and vm.log()
    raise PanicError("trap")

def _op_fallthrough(vm):
    vm.log and vm.log()
    return