from typing import Dict

import numpy as np
from jamcodec.base import JamBytes
from jamcodec.types import U32, U64

from pyjamaz.hashing import blake2b_256_hash

from .constants import HostCallGeneral as op, HostCallResult
from ..graypaper_constants import MAXIMUM_AUTHORIZATION_QUEUE_ITEMS, CORE_COUNT, VALIDATOR_COUNT, \
    MINIMUM_BALANCE_SERVICE, MINIMUM_BALANCE_OCTET, MINIMUM_BALANCE_ITEM, WT, PREIMAGE_EXPUNGE_TIMESLOTS
from ..models.state import ServiceAccount
from ..pvm import PVM


# TODO: er zijn veel register waarden die nu als 64 bit binnenkomen, maar checked moeten worden <=32bit
# TODO: we slaan nu direct resultaat op in bijv pvm registers... wellicht dit eerst in een intermediate state opslaan?
# TODO: bij deleten service, moeten we ook related zaken (FK's, preimages & storageitems) deleten? -> helper functie maken!
# GP_B.??? Accumulate Invocations ΨR
class AccumulateInvocationsMixin:

    def __init__(self):
        #TODO: move to appropiate ServiceAccount class / implement helper&update functions
        self.a_l = 0    #TODO: footprint_storage_items
        self.a_i = 0    #TODO: footprint_storage_bytes
        b_s = MINIMUM_BALANCE_SERVICE
        b_l = MINIMUM_BALANCE_OCTET
        b_i = MINIMUM_BALANCE_ITEM
        self.a_t = b_s + b_i * self.a_i + b_l * self.a_l    #TODO: threshold_balance

    # TODO: x & y eq B.6 & B.7 -> model van maken
    # GP_B.7 The Accumulate host-call
    def bless(self, pvm:PVM, x, y):
        # State transition function for privileged services.
        # (Updates gas limits for privileged services)

        # Privileged services:
        m = pvm.reg[7] # m: index of manager service (manager of chi(X))
        a = pvm.reg[8] # a: index of assign service (authorization queue)
        v = pvm.reg[9] # v: index of designate service (validator queue)

        o = pvm.reg[10] # offset to read service indices and accompanying gas limits from
        n = pvm.reg[11] # number of entries in the auto_accumulate_services dictionary to read

        if pvm.is_readable(pvm.mem, o, o + 12 * n):
            bold_g = {}
            for idx in range(n):
                offset = o + idx * 12
                # s == service_idx
                service_idx = U32(JamBytes(pvm.mem[offset:offset+4]))
                # g == gas
                gas = U64(JamBytes(pvm.mem[offset + 4:offset+4+8]))
                bold_g[service_idx] = gas
        else:
            bold_g = "∇"

        if bold_g == "∇":
            pvm.reg[7] = HostCallResult.oob.value
        #elif any(idx not in pvm.app.service_accounts for idx in [m, a, v]):
        elif any(idx >= 2**32 for idx in [m, a, v]):
            pvm.reg[7] = HostCallResult.who.value
        else:
            pvm.reg[7] = HostCallResult.ok.value
            bold_x_u = x.TODO #TODO: implement blackboard_u = GP.12.13 -> instantiatie van een dataclass
            bold_x_u_bold_x = bold_x_u.privileged_services
            bold_x_u_bold_x.blessed_service = m
            bold_x_u_bold_x.assign_service = a
            bold_x_u_bold_x.designate_service = v
            bold_x_u_bold_x.auto_accumulate_services = bold_g

    def assign(self, pvm:PVM, x, y):
        # Update authorization queue (state transition function of Phi)
        o = pvm.reg[8]   # memory offset
        w7 = pvm.reg[7]  # Core index to update (0..341)

        if pvm.is_readable(pvm.mem, o, o + 32 * MAXIMUM_AUTHORIZATION_QUEUE_ITEMS):
            # Note: bold_c leest voor een specifieke authorization_queue een reeks (Q==80) van authorizations
            bold_c = []
            for idx in range(MAXIMUM_AUTHORIZATION_QUEUE_ITEMS):
                offset = o + idx * 32
                bold_c.append(pvm.mem[offset:offset+32])
        else:
            bold_c = "∇"

        if bold_c == "∇":
            pvm.reg[7] = HostCallResult.oob.value
        elif pvm.reg[7] >= CORE_COUNT:
            pvm.reg[7] = HostCallResult.core.value
        else:
            pvm.reg[7] = HostCallResult.ok.value
            # TODO: wacht tot bold_x & bold_y params zijn gemodeleerd
            bold_x_u = x.TODO  # TODO: implement blackboard_u = GP.12.13
            bold_x_u_bold_q = bold_x_u.authorizations_queue
            bold_x_u_bold_q[w7] = bold_c

    def designate(self, pvm:PVM, x, y):
        # Update the validator Queue (State transition function for the validator queue)
        o = pvm.reg[7]  # offset in memory

        if pvm.is_readable(pvm.mem, o, o + 336 * VALIDATOR_COUNT):
            # bold_v == entire validator_queue state component
            bold_v = []
            for idx in range(MAXIMUM_AUTHORIZATION_QUEUE_ITEMS):
                offset = o + idx * 336
                bold_v.append(pvm.mem[offset:offset+336])
        else:
            bold_v = "∇"

        bold_x_u = x.TODO #TODO: implement blackboard_u = GP.12.13

        if bold_v != "∇":
            pvm.reg[7] = HostCallResult.oob.value
        else:
            pvm.reg[7] = HostCallResult.ok.value
            #TODO: helper functie maken om de validator queue dataclass te updaten op basis vd 336x1023 bytes
            #Note: bold_x_u.validator_queue == bold_x_u_bold_i
            bold_x_u.validator_queue.update(bold_v)  #Note: Update bold_x_u_bold_i

    def checkpoint(self, pvm:PVM, x, y):
        # Set the exeptional dimension y to x (Copy the invocation result context x to y)
        #TODO: helper functie maken: clone_x_to_y(x, y)
        pvm.reg[7] = pvm.gas

    def new(self, pvm:PVM, x, y):
        # Maak nieuwe service aan en registreer deze in de services dictionary
        o = pvm.reg[7]  # offset to read service data from
        l = pvm.reg[8]  # size (byte length) of the code blob TODO: cast of eerste 4 bytes of modulus naar 32bit??
        g = pvm.reg[9]  # gas_limit_accumulate
        m = pvm.reg[10] # gas_limit_on_transfer

        if pvm.is_readable(pvm.mem, o, o + 32):
            # Note: c == code_hash
            c = pvm.mem[o:o+32]
        else:
            c = "∇"

        if c != "∇":
            bold_a = ServiceAccount(
                code_hash=c,
                balance=self.a_t,
                gas_limit_accumulate=g,
                gas_limit_on_transfer=m,
                footprint_storage_items=self.a_l,
                footprint_storage_bytes=self.a_i,
                threshold_balance=self.a_t,
                storage_items={},   #bold_s
                preimages={},   #bold_p
                preimage_availability={(c.tobytes(), l): []}   #bold_l TODO: c+l is een tuple dat de key in de preimage_availability vormt (model change onderhande werk Arjan)
            )
        else:
            bold_a = "∇"

        bold_s = x.service_account  #TODO: levert een service op, zie Eq B.6 & B.7!
        bold_s.balance = bold_a.balance - self.a_t

        if bold_a != "∇" and bold_s.balance >= x.service_account.threshold_balance:
            # TODO: bij updaten service, moeten we ook related zaken (FK's, preimages & storageitems) updaten? -> helper functie maken!
            # NOTE: bij alteren service, dus ook deze state?
            pvm.reg[7] = x.i
            x.i = 2**8 + (x.i - 2**8 + 42) % (2**32 - 2**9) #TODO: wat is dit???? next available service_id??
            x.blackboard_u_TODO.services[x.i] = bold_a  #TODO: voeg nieuwe service met key/value toe?
        elif c == "∇":
            pvm.reg[7] = HostCallResult.oob.value
        else:
            pvm.reg[7] = HostCallResult.cash.value

    def upgrade(self, pvm:PVM, x, y):
        # Updates codehash and gas limits for a service account
        o = pvm.reg[7]  # offset for service codehash
        g = pvm.reg[8]  # gas_limit_accumulate
        m = pvm.reg[9]  # gas_limit_on_transfer

        if pvm.is_readable(pvm.mem, o, o + 32):
            c = pvm.mem[o:o+32]
        else:
            c = "∇"

        if c != "∇":
            x.service_account.code_hash.update(c)
            x.service_account.gas_limit_accumulate.update(g)
            x.service_account.gas_limit_on_transfer.update(m)
            pvm.reg[7] = HostCallResult.ok.value
        else:
            pvm.reg[7] = HostCallResult.oob.value

    def transfer(self, pvm:PVM, x, y):
        # Create a new transfer and add to the defered transfers

        d = pvm.reg[7]      # destination
        a = pvm.reg[8]      # amount
        g = pvm.reg[9]      # gas_limit
        o = pvm.reg[10]     # offset for memo

        gas = 10 + pvm.reg[8] + 2 ** 32 * pvm.reg[9]

        if pvm.is_readable(pvm.mem, o, o + WT):
            m = pvm.mem[o:o + WT]   # Transaction Memo (blob)
            bold_t = Transfer(x.service_index, d, a, m, gas)    #TODO: maak transfer model
        else:
            bold_t = "∇"

        bold_d = x.service_accounts #TODO: vereniging van prestate & intermediate_state???
        b = x.service_account.balance - a

        if bold_t == "∇":
            pvm.reg[7] = HostCallResult.oob.value
        elif d not in bold_d:                           # service index does not exist
            pvm.reg[7] = HostCallResult.who.value
        elif g < bold_d[d].gas_limit_on_transfer:       # our gas limit too low
            pvm.reg[7] = HostCallResult.low.value
        elif pvm.gas < g:                               # gas limit too high
            pvm.reg[7] = HostCallResult.high.value
        elif b < x.service_account.threshold_balance:   # insufficient funds
            pvm.reg[7] = HostCallResult.cash.value
        else:
            pvm.reg[7] = HostCallResult.ok.value
            # TODO: voeg transfer toe???
            # destination=d
            # amount=a,
            # W_r=SCALEENCODE(m)
            # gas_limit=g
            # bold_d.balance -= a
            # update service account???

    def quit(self, pvm:PVM, x, y):
        # Removes a service from the services dictionary in blackboard_U (intermediate state)

        d = pvm.reg[7]     # destination adres
        o = pvm.reg[8]     # memory offset

        x_s = x.service_account
        a =  x_s.balance - x_s.threshold_balance + MINIMUM_BALANCE_SERVICE
        g = pvm.gas
        bold_d = x.service_accounts.get(d, None)  #TODO: fallback lookup naar p=intermediastate

        if d == x.service_index or d == (2**64-1):
            bold_t = "∅"
        elif pvm.is_readable(pvm.mem, o, o + WT):
            m = pvm.mem[o:o + WT]   # Read memo from PVM memory
            bold_t = Transfer(x.service_index, d, a, m, g)  # TODO: Transfer model moet nog worden gemaakt
        else:
            bold_t = "∇"

        bold_s_x_d = x.blackboard_u_TODO.service_accounts  #TODO: levert een service_account dict op, zie Eq B.6 & B.7!

        if bold_t == "∅":
            pvm.reg[7] = HostCallResult.ok.value
            bold_s_x_d.delete(x.service_index)
        elif bold_t == "∇":
            pvm.reg[7] = HostCallResult.oob.value
        elif bold_d is None:
            pvm.reg[7] = HostCallResult.who.value
        elif g < bold_s_x_d.gas_limit_on_transfer:
            pvm.reg[7] = HostCallResult.low.value
        else:
            pvm.reg[7] = HostCallResult.ok.value
            bold_s_x_d.delete(x.service_index)
            # TODO: voeg transfer toe???
            # destination=d
            # amount=a,
            # m=SCALEENCODE(m)
            # gas_limit=g
            # bold_d.balance -= a
            # update service account???


    def solicit(self, pvm:PVM, x, y, t):
        # Modifies the preimage availability lookup (requests a preimage to be made available)
        # TODO: t == timeslot add typing

        o = pvm.reg[7]  # Offset to read preimage hash
        z = pvm.reg[8]  # Part of the preimage availaibility lookup TODO: should always be 32 bit

        if pvm.is_readable(pvm.mem, o, o + 32):
            h = pvm.mem[o:o + 32]
        else:
            h = "∇"

        x_s = x.service_account
        bold_a = clone(x_s) #TODO: maak/gebruik een clone functie

        # TODO: x&y refereren hier naar de cardinaliteit van preimage_availability disctionary, zie 9.2.2 EQ9.7
        if h != "∇" and (h, z) not in x_s.preimage_availability:
            bold_a.preimage_availability.set((h,z), [])     #TODO: implementeer set()
        elif x_s.preimage_availability[h,z] == (x, y):
            bold_a.preimage_availability.set((h, z), t)      #TODO: implementeer set()
        else:
            bold_a = "∇"

        if h == "∇":
            pvm.reg[7] = HostCallResult.oob.value
        elif bold_a == "∇":
            pvm.reg[7] = HostCallResult.huh.value
        elif not bold_a.balance < x_s.threshold_balance:
            pvm.reg[7] = HostCallResult.full.value
        else:
            pvm.reg[7] = HostCallResult.ok.value

    def forget(self, pvm:PVM, x, y, t):
        #doe iets met preimage availability dict attribuut van een serviceaccount
        # TODO: t == timeslot add typing

        o = pvm.reg[7]     # Offset for preimage hash
        z = pvm.reg[8]     # primage u32 key

        if pvm.is_readable(pvm.mem, o, o + 32):
            h = pvm.mem[o:o + 32]
        else:
            h = "∇"

        x_s = x.service_accounts
        x_s_l = x_s.preimage_availability
        x_s_p = x_s.preimages
        bold_a = clone(x_s) #TODO: maak/gebruik een clone functie

        #bold_a_l = x_s_l.get((h, z))

        #TODO: x&y&w refereren hier naar de cardinaliteit van preimage_availability disctionary, zie 9.2.2 EQ9.7
        if x_s_l is None or x_s_l[(h,z)] == (y,z) and y < t - PREIMAGE_EXPUNGE_TIMESLOTS:
            bold_a.preimage_availability.remove((h, z)) #TODO: implement .remove
            bold_a.preimages.remove(h)  #TODO: implement .remove
        elif bold_a_l == 1:
            bold_x_s.preimage_availability[(h, z)].add(t)   #TODO: implementeer!
        elif bold_a_l == [x,y,w] and y < t - TMP_CONST.D:
            bold_x_s.preimage_availability[(h, z)].add(t)  # TODO: implementeer!
        else:
            bold_a = "∇"

        if h == "∇":
            pvm.reg[7] = HostCallResult.oob.value
        elif bold_a == "∇":
            pvm.reg[7] = HostCallResult.huh.value
        else:
            pvm.reg[7] = HostCallResult.ok.value
