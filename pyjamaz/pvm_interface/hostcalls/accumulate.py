from pyjamaz.pvm.constants import ExitReason


class AccumulateInvocation:

    def __init__(self):
        pass

    # def upgrade(self, gas, registers, memory, bold_x, bold_y):
    #     # Updates codehash and gas limits for a service account
    #     o = registers[7]  # offset for service codehash
    #     g = registers[8]  # gas_limit_accumulate
    #     m = registers[9]  # gas_limit_on_transfer
    #
    #     if memory.is_readable(memory.data, o, o + 32):
    #         c = memory.data[o:o+32]
    #     else:
    #         c = "∇"
    #
    #     if c != "∇":
    #         return (
    #             ExitReason.halt,
    #             bold_x.service_account.code_hash.update(c),
    #             bold_x.service_account.gas_limit_accumulate.update(g),
    #             bold_x.service_account.gas_limit_on_transfer.update(m),
    #         )
    #     else:
    #         return (
    #
    #         )

#     def new(self, pvm:PVM, x, y):
#         # Maak nieuwe service aan en registreer deze in de services dictionary
#         o = pvm.reg[7]  # offset to read service data from
#         l = pvm.reg[8]  # size (byte length) of the code blob TODO: cast of eerste 4 bytes of modulus naar 32bit??
#         g = pvm.reg[9]  # gas_limit_accumulate
#         m = pvm.reg[10] # gas_limit_on_transfer
#
#         if pvm.is_readable(pvm.mem, o, o + 32):
#             # Note: c == code_hash
#             c = pvm.mem[o:o+32]
#         else:
#             c = "∇"
#
#         if c != "∇":
#             bold_a = ServiceAccount(
#                 code_hash=c,
#                 balance=self.a_t,
#                 gas_limit_accumulate=g,
#                 gas_limit_on_transfer=m,
#                 footprint_storage_items=self.a_l,
#                 footprint_storage_bytes=self.a_i,
#                 threshold_balance=self.a_t,
#                 storage_items={},   #bold_s
#                 preimages={},   #bold_p
#                 preimage_availability={(c.tobytes(), l): []}   #bold_l TODO: c+l is een tuple dat de key in de preimage_availability vormt (model change onderhande werk Arjan)
#             )
#
#         else:
#             bold_a = "∇"
#
#         bold_s = x.service_account  #TODO: levert een service op, zie Eq B.6 & B.7!
#         bold_s.balance = bold_a.balance - self.a_t
#
#         if bold_a != "∇" and bold_s.balance >= x.service_account.threshold_balance:
#             # TODO: bij updaten service, moeten we ook related zaken (FK's, preimages & storageitems) updaten? -> helper functie maken!
#             # NOTE: bij alteren service, dus ook deze state?
#             pvm.reg[7] = x.i
#             x.i = 2**8 + (x.i - 2**8 + 42) % (2**32 - 2**9) #TODO: HELPER FUNCTIES CHECK & BUMP IMPLEMENTEREN
#             x.blackboard_u_TODO.services[x.i] = bold_a  #TODO: voeg nieuwe service met key/value toe?
#         elif c == "∇":
#             pvm.reg[7] = HostCallResult.oob.value
#         else:
#             pvm.reg[7] = HostCallResult.cash.value
#


# from typing import Dict
#
# import numpy as np
# from jamcodec.base import JamBytes
# from jamcodec.types import U32, U64
#
# from pyjamaz.hashing import blake2b_256_hash
#
# from .constants import HostCallGeneral as op, HostCallResult
# from ..graypaper_constants import MAXIMUM_AUTHORIZATION_QUEUE_ITEMS, CORE_COUNT, VALIDATOR_COUNT, \
#     MINIMUM_BALANCE_SERVICE, MINIMUM_BALANCE_OCTET, MINIMUM_BALANCE_ITEM, WT, PREIMAGE_EXPUNGE_TIMESLOTS
# from ..models.state import ServiceAccount
# from ..pvm import PVM
#
#
# # TODO: er zijn veel register waarden die nu als 64 bit binnenkomen, maar checked moeten worden <=32bit
# # TODO: we slaan nu direct resultaat op in bijv pvm registers... wellicht dit eerst in een intermediate state opslaan?
# # TODO: bij deleten service, moeten we ook related zaken (FK's, preimages & storageitems) deleten? -> helper functie maken!
# # GP_B.??? Accumulate Invocations ΨR
# class AccumulateInvocationsMixin:
#
#     def __init__(self):
#         #TODO: move to appropiate ServiceAccount class / implement helper&update functions
#         self.a_l = 0    #TODO: footprint_storage_items
#         self.a_i = 0    #TODO: footprint_storage_bytes
#         b_s = MINIMUM_BALANCE_SERVICE
#         b_l = MINIMUM_BALANCE_OCTET
#         b_i = MINIMUM_BALANCE_ITEM
#         self.a_t = b_s + b_i * self.a_i + b_l * self.a_l    #TODO: threshold_balance
#
#     # 5
#     # TODO: x & y eq B.6 & B.7 -> model van maken
#     # GP_B.7 The Accumulate host-call
#     def bless(self, pvm:PVM, x, y):
#         # State transition function for privileged services.
#         # (Updates gas limits for privileged services)
#
#         # Privileged services:
#         m = pvm.reg[7] # m: index of manager service (manager of chi(X))
#         a = pvm.reg[8] # a: index of assign service (authorization queue)
#         v = pvm.reg[9] # v: index of designate service (validator queue)
#
#         o = pvm.reg[10] # offset to read service indices and accompanying gas limits from
#         n = pvm.reg[11] # number of entries in the auto_accumulate_services dictionary to read
#
#         if pvm.is_readable(pvm.mem, o, o + 12 * n):
#             bold_g = {}
#             for idx in range(n):
#                 offset = o + idx * 12
#                 # s == service_idx
#                 service_idx = U32(JamBytes(pvm.mem[offset:offset+4]))
#                 # g == gas
#                 gas = U64(JamBytes(pvm.mem[offset + 4:offset+4+8]))
#                 bold_g[service_idx] = gas
#         else:
#             bold_g = "∇"
#
#         if bold_g == "∇":
#             pvm.reg[7] = HostCallResult.oob.value
#         #elif any(idx not in pvm.app.service_accounts for idx in [m, a, v]):
#         elif any(idx >= 2**32 for idx in [m, a, v]):
#             pvm.reg[7] = HostCallResult.who.value
#         else:
#             pvm.reg[7] = HostCallResult.ok.value
#             bold_x_u = x.TODO #TODO: implement blackboard_u = GP.12.13 -> instantiatie van een dataclass
#             bold_x_u_bold_x = bold_x_u.privileged_services
#             bold_x_u_bold_x.blessed_service = m
#             bold_x_u_bold_x.assign_service = a
#             bold_x_u_bold_x.designate_service = v
#             bold_x_u_bold_x.auto_accumulate_services = bold_g
#
#     # 6
#     def assign(self, pvm:PVM, x, y):
#         # Update authorization queue (state transition function of Phi)
#         o = pvm.reg[8]   # memory offset
#         w7 = pvm.reg[7]  # Core index to update (0..341)
#
#         if pvm.is_readable(pvm.mem, o, o + 32 * MAXIMUM_AUTHORIZATION_QUEUE_ITEMS):
#             # Note: bold_c leest voor een specifieke authorization_queue een reeks (Q==80) van authorizations
#             bold_c = []
#             for idx in range(MAXIMUM_AUTHORIZATION_QUEUE_ITEMS):
#                 offset = o + idx * 32
#                 bold_c.append(pvm.mem[offset:offset+32])
#         else:
#             bold_c = "∇"
#
#         if bold_c == "∇":
#             pvm.reg[7] = HostCallResult.oob.value
#         elif pvm.reg[7] >= CORE_COUNT:
#             pvm.reg[7] = HostCallResult.core.value
#         else:
#             pvm.reg[7] = HostCallResult.ok.value
#             # TODO: wacht tot bold_x & bold_y params zijn gemodeleerd
#             bold_x_u = x.TODO  # TODO: implement blackboard_u = GP.12.13
#             bold_x_u_bold_q = bold_x_u.authorizations_queue
#             bold_x_u_bold_q[w7] = bold_c
#
#     # 7
#     def designate(self, pvm:PVM, x, y):
#         # Update the validator Queue (State transition function for the validator queue)
#         o = pvm.reg[7]  # offset in memory
#
#         if pvm.is_readable(pvm.mem, o, o + 336 * VALIDATOR_COUNT):
#             # bold_v == entire validator_queue state component
#             bold_v = []
#             for idx in range(MAXIMUM_AUTHORIZATION_QUEUE_ITEMS):
#                 offset = o + idx * 336
#                 bold_v.append(pvm.mem[offset:offset+336])
#         else:
#             bold_v = "∇"
#
#         bold_x_u = x.TODO #TODO: implement blackboard_u = GP.12.13
#
#         if bold_v != "∇":
#             pvm.reg[7] = HostCallResult.oob.value
#         else:
#             pvm.reg[7] = HostCallResult.ok.value
#             #TODO: helper functie maken om de validator queue dataclass te updaten op basis vd 336x1023 bytes
#             #Note: bold_x_u.validator_queue == bold_x_u_bold_i
#             bold_x_u.validator_queue.update(bold_v)  #Note: Update bold_x_u_bold_i
#
#     # 8
#     def checkpoint(self, pvm:PVM, x, y):
#         # Set the exeptional dimension y to x (Copy the invocation result context x to y)
#         #TODO: helper functie maken: clone_x_to_y(x, y)
#         pvm.reg[7] = pvm.gas
#
#     # 9
#     def new(self, pvm:PVM, x, y):
#         # Maak nieuwe service aan en registreer deze in de services dictionary
#         o = pvm.reg[7]  # offset to read service data from
#         l = pvm.reg[8]  # size (byte length) of the code blob TODO: cast of eerste 4 bytes of modulus naar 32bit??
#         g = pvm.reg[9]  # gas_limit_accumulate
#         m = pvm.reg[10] # gas_limit_on_transfer
#
#         if pvm.is_readable(pvm.mem, o, o + 32):
#             # Note: c == code_hash
#             c = pvm.mem[o:o+32]
#         else:
#             c = "∇"
#
#         if c != "∇":
#             bold_a = ServiceAccount(
#                 code_hash=c,
#                 balance=self.a_t,
#                 gas_limit_accumulate=g,
#                 gas_limit_on_transfer=m,
#                 footprint_storage_items=self.a_l,
#                 footprint_storage_bytes=self.a_i,
#                 threshold_balance=self.a_t,
#                 storage_items={},   #bold_s
#                 preimages={},   #bold_p
#                 preimage_availability={(c.tobytes(), l): []}   #bold_l TODO: c+l is een tuple dat de key in de preimage_availability vormt (model change onderhande werk Arjan)
#             )
#
#         else:
#             bold_a = "∇"
#
#         bold_s = x.service_account  #TODO: levert een service op, zie Eq B.6 & B.7!
#         bold_s.balance = bold_a.balance - self.a_t
#
#         if bold_a != "∇" and bold_s.balance >= x.service_account.threshold_balance:
#             # TODO: bij updaten service, moeten we ook related zaken (FK's, preimages & storageitems) updaten? -> helper functie maken!
#             # NOTE: bij alteren service, dus ook deze state?
#             pvm.reg[7] = x.i
#             x.i = 2**8 + (x.i - 2**8 + 42) % (2**32 - 2**9) #TODO: HELPER FUNCTIES CHECK & BUMP IMPLEMENTEREN
#             x.blackboard_u_TODO.services[x.i] = bold_a  #TODO: voeg nieuwe service met key/value toe?
#         elif c == "∇":
#             pvm.reg[7] = HostCallResult.oob.value
#         else:
#             pvm.reg[7] = HostCallResult.cash.value
#
#     # 10
#     def upgrade(self, gas, registers, memory, bold_x, bold_y):
#         # Updates codehash and gas limits for a service account
#         o = registers[7]  # offset for service codehash
#         g = registers[8]  # gas_limit_accumulate
#         m = registers[9]  # gas_limit_on_transfer
#
#         if memory.is_readable(memory.data, o, o + 32):
#             c = memory.data[o:o+32]
#         else:
#             c = "∇"
#
#         if c != "∇":
#             return (
#                 HostCallResult.cash.value,
#                 bold_x.service_account.code_hash.update(c),
#                 bold_x.service_account.gas_limit_accumulate.update(g),
#                 bold_x.service_account.gas_limit_on_transfer.update(m),
#                 registers[7] = HostCallResult.ok.value
#             )
#         else:
#             #pvm.reg[7] = HostCallResult.oob.value
#
#     # 11
#     def transfer(self, pvm:PVM, x, y):
#         # Create a new transfer and add to the defered transfers
#
#         d = pvm.reg[7]      # destination
#         a = pvm.reg[8]      # amount
#         g = pvm.reg[9]      # gas_limit
#         o = pvm.reg[10]     # offset for memo
#
#         # Note: seems to result in a very big number unless w_8 or w_9 is negative?
#         g = 10 + pvm.reg[8] + 2 ** 32 * g
#
#         # TODO: vereniging van prestate & intermediate_state -> wacht op intermediate state (backboard_u)
#         bold_d = x.service_accounts
#
#         if pvm.is_readable(pvm.mem, o, o + SIZE_TRANSFER_MEMO):
#             m = pvm.mem[o:o + SIZE_TRANSFER_MEMO]   # Transaction Memo (blob)
#             bold_t = DeferredTransfer(x.service_index, d, a, m, g)    #TODO: maak transfer model
#         else:
#             bold_t = "∇"
#
#         b = x.service_account.balance - a
#
#         if bold_t == "∇":
#             pvm.reg[7] = HostCallResult.oob.value
#         elif d not in bold_d:                           # service index does not exist
#             pvm.reg[7] = HostCallResult.who.value
#         elif g < bold_d[d].gas_limit_on_transfer:       # our gas limit too low
#             pvm.reg[7] = HostCallResult.low.value
#         elif pvm.gas < g:                               # gas limit too high
#             pvm.reg[7] = HostCallResult.high.value
#         elif b < x.service_account.threshold_balance:   # insufficient funds
#             pvm.reg[7] = HostCallResult.cash.value
#         else:
#             pvm.reg[7] = HostCallResult.ok.value
#             # TODO: voeg transfer toe aan de deferred_transfers in intermediate state (X)
#
#     #12
#     def eject(self, pvm:PVM, bold_x, bold_y, t):
#         d = pvm.reg[7]      # destination
#         o = pvm.reg[8]      #
#
#         # h = preimage_hash
#         if pvm.is_readable(pvm.mem, o, o + 32):
#             h = pvm.mem[o:o+32]
#         else:
#             h = "∇"
#
#         #bold_d == service_account
#         if d != bold_x.service_id and d in bold_x.state_context.services:
#             bold_d = bold_x.state_context.service_accounts.get(d, None)  #TODO: fallback lookup naar p=intermediastate
#
#         # ...verwijder de service uit de service dictionary
#
#
#     #13
#     def query(self, pvm:PVM, x, y):
#         """
#         (xs)l[h,z] == preimage_availability
#         bepaalt de beschikbaarheid van de preimage
#         """
#         pass
#
#
#     # def quit(self, pvm:PVM, x, y):
#     #     # Removes a service from the services dictionary in blackboard_U (intermediate state)
#     #
#     #     d = pvm.reg[7]     # destination adres
#     #     o = pvm.reg[8]     # memory offset
#     #
#     #     x_s = x.service_account
#     #     a =  x_s.balance - x_s.threshold_balance + MINIMUM_BALANCE_SERVICE
#     #     g = pvm.gas
#     #     bold_d = x.service_accounts.get(d, None)  #TODO: fallback lookup naar p=intermediastate
#     #
#     #     if d in (x.service_index, (2**64-1)): # Note: 2**64-1 means None
#     #         bold_t = "∅"
#     #     elif pvm.is_readable(pvm.mem, o, o + SIZE_TRANSFER_MEMO):
#     #         m = pvm.mem[o:o + SIZE_TRANSFER_MEMO]   # Read memo from PVM memory
#     #         bold_t = DeferredTransfer(x.service_index, d, a, m, g)  # TODO: Transfer model moet nog worden gemaakt
#     #     else:
#     #         bold_t = "∇"
#     #
#     #     bold_s_x_d = x.blackboard_u_TODO.service_accounts  #TODO: levert een service_account dict op, zie Eq B.6 & B.7!
#     #
#     #     if bold_t == "∅":
#     #         pvm.reg[7] = HostCallResult.ok.value
#     #         bold_s_x_d.delete(x.service_index)
#     #     elif bold_t == "∇":
#     #         pvm.reg[7] = HostCallResult.oob.value
#     #     elif d not in bold_d:
#     #         pvm.reg[7] = HostCallResult.who.value
#     #     elif g < bold_d[d].gas_limit_on_transfer:
#     #         pvm.reg[7] = HostCallResult.low.value
#     #     else:
#     #         pvm.reg[7] = HostCallResult.ok.value
#     #         bold_s_x_d.delete(x.service_index)
#     #         # TODO: voeg transfer toe aan de deferred_transfers in intermediate state (X)
#
#
#     #14
#     def solicit(self, pvm:PVM, x, y, t):
#         # Modifies the preimage availability lookup (requests a preimage to be made available)
#         # TODO: t == timeslot add typing
#
#         o = pvm.reg[7]  # Offset to read preimage hash
#         z = pvm.reg[8]  # Part of the preimage availaibility lookup TODO: should always be 32 bit
#
#         if pvm.is_readable(pvm.mem, o, o + 32):
#             h = pvm.mem[o:o + 32]
#         else:
#             h = "∇"
#
#         x_s = x.service_account
#         bold_a = TODO_clone(x_s) #TODO: maak/gebruik een clone functie
#
#         # TODO: x&y refereren hier naar de cardinaliteit van preimage_availability disctionary, zie 9.2.2 EQ9.7
#         if h != "∇" and not (h, z) in x_s.preimage_availability:
#             # Note: Request of a preimage (preimage not yet supplied)
#             bold_a.preimage_availability.set((h,z), [])     #TODO: implementeer set()
#         elif len(x_s.preimage_availability[h,z]) == 2:
#             # Note: Remake a preimage available again
#             # Note: Add attribute header.timeslot from provided argument
#             bold_a.preimage_availability.append((h, z), t)      #TODO: implementeer set()
#         else:
#             bold_a = "∇"
#
#         if h == "∇":
#             pvm.reg[7] = HostCallResult.oob.value
#         elif bold_a == "∇":
#             pvm.reg[7] = HostCallResult.huh.value
#         elif not bold_a.balance < x_s.threshold_balance:
#             pvm.reg[7] = HostCallResult.full.value
#         else:
#             pvm.reg[7] = HostCallResult.ok.value
#
#     #15
#     def forget(self, pvm:PVM, x, y, t):
#         #doe iets met preimage availability dict attribuut van een serviceaccount
#         # TODO: t == timeslot add typing
#
#         o = pvm.reg[7]     # Offset for preimage hash
#         z = pvm.reg[8]     # preimage u32 key
#
#         if pvm.is_readable(pvm.mem, o, o + 32):
#             h = pvm.mem[o:o + 32]
#         else:
#             h = "∇"
#
#         x_s = x.service_accounts
#         x_s_l = x_s.preimage_availability
#         x_s_p = x_s.preimages
#         bold_a = TODO_clone(x_s) #TODO: maak/gebruik een clone functie
#
#         #bold_a_l = x_s_l.get((h, z))
#
#         #TODO: x&y&w refereren hier naar de cardinaliteit van preimage_availability disctionary, zie 9.2.2 EQ9.7
#         preimage_availability = x_s_l[(h,z)]
#         cardinality = len(preimage_availability)
#         if cardinality == 0 or (cardinality == 2 and preimage_availability[1] < t - PREIMAGE_EXPUNGE_TIMESLOTS):
#             bold_a.preimage_availability.remove((h, z)) #TODO: implement .remove
#             bold_a.preimages.remove(h)  #TODO: implement .remove
#         elif cardinality == 1:
#             bold_a.preimage_availability[(h, z)].append(t)   #TODO: implementeer!
#         elif cardinality == 3 and y < t - PREIMAGE_EXPUNGE_TIMESLOTS:
#             # Note: reset unreferenced preimage expunge time with current timeslot
#             bold_a.preimage_availability[(h, z)].set([x_s_l[2], t])   # TODO: implementeer!
#         else:
#             bold_a = "∇"
#
#         if h == "∇":
#             pvm.reg[7] = HostCallResult.oob.value
#         elif bold_a == "∇":
#             pvm.reg[7] = HostCallResult.huh.value
#         else:
#             pvm.reg[7] = HostCallResult.ok.value
#
#     #16
#     def _yield(self):
#         """
#         haalt 32 bytes uit geheugen en geeft dit terug (een preimage hash)
#         """
#         pass
