from typing import List

from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.pvm.invocation import InvocationMutationOutput
from pyjamaz.pvm.types import PVMLogger, PVMMemory


# def hc_historical_lookup(
#         registers: List[int],
#         memory: PVMMemory,
#         m_e: RefineInvocationContext,
#         timeslot,
#         invocation_output: InvocationMutationOutput,
#         logger: PVMLogger):
#
#     # haal preimage op adv serviceaccount, timeslot en preimagehash en schrijf (deel?) deze weg in memory
#     # logger.hc_regs(f"HISTORICAL_LOOKUP", "refine")
#     # invocation_output.gas_limit -= 10
#     #
#     # services = ctx_in.context.services
#     # service_id = ctx_in.context.service_account_id
#     # try:
#     #     service_account = services.retrieve_service_account(service_id)  # GP: bold_a
#     # except StateKeyNoResult:
#     #     service_account = None
#     #
#     # service_account_id = registers[7]
#     # if service_account_id in (service_id, 2 ** 64 - 1):
#     #     service_account_id = service_id
#     #     service_account = service_account
#     # else:
#     #     try:
#     #         service_account = services.retrieve_service_account(registers[7])  # GP: bold_a
#     #     except StateKeyNoResult:
#     #         service_account = None  # bold_a = ∅
#
#     # lambda(a,t,mem+32) (EQ 9.5), historical lookup
#
#
# # def hc_fetch(ctx_in: InvocationInput, ctx_out: InvocationMutationOutput, logger: PVMLogger): raise Exception("TODO: implement!!!!!!!")
# # i == index of the workitem to be refined
# # p == workpackage
# # bold_o == authorizer output
# # i_flat == all workitems' import segments
# # bold_v: generieke -> bytes
# #       serialized(p) workpackage == bytes
# #       authorizer output == bytes
# #       Pw == sequence of workitems (eq:14.2), Pw.y == WorkItemn == bytes
# #       bold_x == Pw.x == WorkItemExtrinsic == bytes
# #       i_flat == all workitems' import segments == bytes
# #       Pp == parameterization blob == bytes
# #
# # op basis van register 10 gaan we v ophalen en schrijven we dit weg in memory
#
#
# # def hc_export(ctx_in: InvocationInput, ctx_out: InvocationMutationOutput, logger: PVMLogger): raise Exception("TODO: implement!!!!!!!")
# # leest iets uit geheugen en append een blob toe aan e (export segments)
# # Wg == 4104 (constant)
# # P(Wg) == padded wg
# # e == export segments
# # c_cedie == export segment offset
#
#
# # def hc_machine(ctx_in: InvocationInput, ctx_out: InvocationMutationOutput, logger: PVMLogger): raise Exception("TODO: implement!!!!!!!")
# # zet een programma blob met mem en startpos in program dictionary (bold_m) -> memory is inaccessible
#
#
# # def hc_peek(ctx_in: InvocationInput, ctx_out: InvocationMutationOutput, logger: PVMLogger): raise Exception("TODO: implement!!!!!!!")
# # kijkt in een pvm instance (r0) memory, en plaatst dit in huidig pvm mem??
#
#
# # def hc_poke(ctx_in: InvocationInput, ctx_out: InvocationMutationOutput, logger: PVMLogger): raise Exception("TODO: implement!!!!!!!")
# # kijkt in huidig pvm mem en plaatst dit in andere pvms mem
#
#
# # def hc_zero(ctx_in: InvocationInput, ctx_out: InvocationMutationOutput, logger: PVMLogger): raise Exception("TODO: implement!!!!!!!")
# # vult een pvm instances memory met 0 of W
# # maakt dit geheugen toegankelijk(writable) -> zie hc_machine
#
#
# # def hc_void(ctx_in: InvocationInput, ctx_out: InvocationMutationOutput, logger: PVMLogger): raise Exception("TODO: implement!!!!!!!")
# # vult een pvm instances memory met 0 of maakt het inaccesible?
# #TODO: accessibility per page kunnen aangeven!!!!!!
#
#
# # def hc_invoke(ctx_in: InvocationInput, ctx_out: InvocationMutationOutput, logger: PVMLogger): raise Exception("TODO: implement!!!!!!!")
# # doet een nieuwe pvm invoke? en vervangt pvm memory en update de program counter van pvm n??
#
#
# # def hc_expunge(ctx_in: InvocationInput, ctx_out: InvocationMutationOutput, logger: PVMLogger): raise Exception("TODO: implement!!!!!!!")
# # verwijderd een pvm instance
