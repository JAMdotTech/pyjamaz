# import os
# import subprocess
# import sys
# import unittest
# from copy import deepcopy
# from pathlib import Path
# from types import SimpleNamespace
# from unittest.mock import patch
#
# import numpy as np
#
# from pyjamaz import settings
# from pyjamaz.graypaper_constants import CORE_COUNT
# from pyjamaz.hostcalls.accumulate import hc_bless
# from pyjamaz.hostcalls.constants import HostCallResult
# from pyjamaz.models.state import PrivilegedServicesState
# from pyjamaz.pvm import PVMMemory
# from pyjamaz.pvm.constants import ExitCondition, ExitReason, MEM_R
# from pyjamaz.pvm.invocation import InvocationMutationOutput
#
#
# class TestBlessCompatibility(unittest.TestCase):
#     def invoke(self, *, compatibility=False, version="0.8.0", caller=2,
#                overrides=None, gas=1000):
#         privileges = PrivilegedServicesState(
#             manager=1, assigners=[1] * CORE_COUNT, delegator=2,
#             registrar=3, always_accumulators={4: 100},
#         )
#         before = deepcopy(privileges)
#         context = SimpleNamespace(context=SimpleNamespace(
#             service_account_id=caller,
#             state_context=SimpleNamespace(privileged_services=privileges),
#         ))
#         address = 131072
#         assigners = b"".join((20 + core).to_bytes(4, "little") for core in range(CORE_COUNT))
#         auto_accumulate = (40).to_bytes(4, "little") + (500).to_bytes(8, "little")
#         memory = PVMMemory()
#         memory.add_segment(address, 4096, MEM_R, (assigners + auto_accumulate).ljust(4096, b"\0"))
#         registers = [0] * 13
#         registers[7:13] = [10, address, 30, 31, address + len(assigners), 1]
#         for index, value in (overrides or {}).items():
#             registers[index] = value
#         output = InvocationMutationOutput(
#             exit_condition=ExitCondition(reason=ExitReason.resume),
#             gas_limit=gas,
#             registers=np.array(registers, dtype=np.uint64),
#             memory=memory,
#         )
#         with patch.object(settings, "GP080_NON_MANAGER_BLESS_COMPAT", compatibility), \
#                 patch.object(settings, "GP_VERSION", version):
#             hc_bless(registers, memory, context, output, None)
#         return before, privileges, output
#
#     def assert_success(self, privileges, output):
#         self.assertEqual(output.exit_condition.reason, ExitReason.resume)
#         self.assertEqual(output.registers[7], HostCallResult.OK.value)
#         self.assertEqual(output.gas_limit, 558)
#         self.assertEqual(privileges, PrivilegedServicesState(
#             manager=10, assigners=[20 + core for core in range(CORE_COUNT)],
#             delegator=30, registrar=31, always_accumulators={40: 500},
#         ))
#
#     def test_environment_requires_explicit_one(self):
#         for value, expected in ((None, "False"), ("0", "False"), ("true", "False"), ("1", "True")):
#             with self.subTest(value=value):
#                 environment = os.environ.copy()
#                 environment.pop("GP080_NON_MANAGER_BLESS_COMPAT", None)
#                 if value is not None:
#                     environment["GP080_NON_MANAGER_BLESS_COMPAT"] = value
#                 actual = subprocess.check_output(
#                     [sys.executable, "-B", "-c",
#                      "from pyjamaz.settings import GP080_NON_MANAGER_BLESS_COMPAT; "
#                      "print(GP080_NON_MANAGER_BLESS_COMPAT)"],
#                     cwd=Path(__file__).resolve().parents[1], env=environment, text=True,
#                 ).strip()
#                 self.assertEqual(actual, expected)
#
#     def test_non_manager_rejected_by_default(self):
#         before, privileges, output = self.invoke()
#         self.assertEqual(output.exit_condition.reason, ExitReason.resume)
#         self.assertEqual(output.registers[7], HostCallResult.HUH.value)
#         self.assertEqual(output.gas_limit, 558)
#         self.assertEqual(privileges, before)
#
#     def test_non_manager_accepted_with_opt_in(self):
#         _, privileges, output = self.invoke(compatibility=True)
#         self.assert_success(privileges, output)
#
#     def test_manager_unaffected_by_flag(self):
#         for compatibility in (False, True):
#             with self.subTest(compatibility=compatibility):
#                 _, privileges, output = self.invoke(compatibility=compatibility, caller=1)
#                 self.assert_success(privileges, output)
#
#     def test_compatibility_is_limited_to_gp080(self):
#         for version in ("0.7.2", "0.8.1"):
#             with self.subTest(version=version):
#                 before, privileges, output = self.invoke(compatibility=True, version=version)
#                 self.assertEqual(output.exit_condition.reason, ExitReason.resume)
#                 self.assertEqual(output.registers[7], HostCallResult.HUH.value)
#                 self.assertEqual(privileges, before)
#
#     def test_invalid_memory_still_panics(self):
#         for compatibility in (False, True):
#             for caller in (1, 2):
#                 for register in (8, 11):
#                     with self.subTest(compatibility=compatibility, caller=caller, register=register):
#                         before, privileges, output = self.invoke(
#                             compatibility=compatibility, caller=caller,
#                             overrides={register: 262144},
#                         )
#                         self.assertEqual(output.exit_condition.reason, ExitReason.panic)
#                         self.assertEqual(privileges, before)
#
#     def test_invalid_service_ids_still_rejected(self):
#         cases = (
#             (False, 1, HostCallResult.WHO),
#             (False, 2, HostCallResult.HUH),
#             (True, 1, HostCallResult.WHO),
#             (True, 2, HostCallResult.WHO),
#         )
#         for compatibility, caller, result in cases:
#             for register in (7, 9, 10):
#                 with self.subTest(compatibility=compatibility, caller=caller, register=register):
#                     before, privileges, output = self.invoke(
#                         compatibility=compatibility, caller=caller,
#                         overrides={register: 2 ** 32},
#                     )
#                     self.assertEqual(output.exit_condition.reason, ExitReason.resume)
#                     self.assertEqual(output.registers[7], result.value)
#                     self.assertEqual(privileges, before)
#
#     def test_out_of_gas_still_prevents_mutation(self):
#         for compatibility in (False, True):
#             with self.subTest(compatibility=compatibility):
#                 before, privileges, output = self.invoke(compatibility=compatibility, gas=441)
#                 self.assertEqual(output.exit_condition.reason, ExitReason.out_of_gas)
#                 self.assertEqual(output.registers[7], 10)
#                 self.assertEqual(privileges, before)
#
#
# if __name__ == "__main__":
#     unittest.main()
