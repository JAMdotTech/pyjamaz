from typing import Dict

import numpy as np
from jamcodec.types import U32

from pyjamaz.hashing import blake2b_256_hash

from .constants import HostCallGeneral as op, HostCallResult
from .exceptions import InvalidHostCall
from ..models.state import ServiceAccount
from ..pvm import PVM


# TODO: we slaan nu direct resultaat op in bijv pvm registers... wellicht dit eerst in een intermediate state opslaan?
# GP_B.6 General Functions
class GeneralFunctionsMixin:

    def gas(self, pvm:PVM, bold_s:ServiceAccount=None, s:int=None, d:Dict[int, ServiceAccount]=None):
        """
        Puts available PVM gas in register 7
        """
        pvm.gas -= 10
        pvm.reg[7] = pvm.gas

    # bold_s: Service, s: ServiceIndex, d:ServiceLookup
    #(ϱ:Gas, ω:Pvm_registers, µ:pvm_memory, bold_s:Service, s:ServiceIndex, d:ServiceDict) K:element of???  H:scale encoded?????
    def lookup(self, pvm:PVM, bold_s:ServiceAccount=None, s:int=None, bold_d:Dict[int, ServiceAccount]=None):
        """
        Puts a Service Preimage blob into PVM memory
        """
        pvm.gas -= 10
        #TODO: alle register variabelen w vervangen in ω
        #w7==service_account_index
        w7 = pvm.reg[7]
        if w7 in (s, 2 ** 64 - 1):
            #bold_a==ServiceAccount
            bold_a = bold_s
        else:
            bold_a = bold_d.get_service_account(w7) #TODO: implementeer ServicesState.get_service_account

        h_o = pvm.reg[8]  # offset to read image hash from pvm mem
        b_o = pvm.reg[9]  # offset to write image data to in pvm mem
        b_z = pvm.reg[10]  # max length to write in pvm mem

        if pvm.is_readable(pvm.mem, h_o, h_o + 32):
            #h==preimage_hash
            #TODO: why do we hash over 32 bytes? isnt this already a hash in memory?
            h = blake2b_256_hash(pvm.mem[h_o:h_o + 32]) # create the preimage hash
        else:
            h = "∇"     #TODO: is eigenlijk geheugen niet leesbaar error code, overal toepassen?

        if bold_a and bold_a.preimages.has_preimage_key(h):    #TODO: implementeer de lookup functie voor deze key
            #bold_v==preimage code blob
            bold_v = bold_a.preimages.get_preimage_value(h)    #TODO: service_account.preimages.get_preimage_value implementeren!
        else:
            bold_v = "∅"    #TODO: is eigenlijk None, overal toepassen?

        # Note: b_o & b_z are defined as elements of Z, while PVM registers are defined as elements of N,
        # either Z is incorrect or we need a pvm_Z conversion
        if bold_v != "∅" and pvm.is_writable(pvm.mem, b_o, b_o + b_z):
            nr_bytes = min(b_z, len(bold_v))
            pvm.mem[b_o:b_o + nr_bytes] = np.frombuffer(bold_v[:nr_bytes], dtype=np.uint8)
        else:
            # Note: Memory unchanged
            pass

        if h != "∇" and pvm.is_writable(pvm.mem, b_o, b_o + b_z):
            if bold_v == "∅":
                pvm.reg[7] = HostCallResult.none.value
            else:
                pvm.reg[7] = len(bold_v)
        else:
            pvm.reg[7] = HostCallResult.oob.value

    def read(self, pvm:PVM, bold_s:ServiceAccount=None, s:int=None, bold_d:Dict[int, ServiceAccount]=None):
        """
        Puts a Service StorageItem blob into PVM memory
        """
        pvm.gas -= 10

        #TODO: inconsistentie met de lookup hostfuntie, waarschijnlijk moet GP aangepast worden (lookup gelijk maken aan read)
        w7 = pvm.reg[7]
        if w7 in (s, 2 ** 64 - 1):
            bold_a = bold_s
        elif w7 in bold_d:
            bold_a = bold_d.get_service_account(w7)
        else:
            bold_a = "∅"

        k_o = pvm.reg[8]  # offset to read from memory
        k_z = pvm.reg[9]  # length to read from memory
        b_o = pvm.reg[10]  # offset where to write to in pvm mem
        b_z = pvm.reg[11]  # max length to write in pvm mem

        if pvm.is_readable(pvm.mem, k_o, k_o + k_z):
            # Note: k == storage item key hash
            # TODO: use jam codec (catagorie premature optimalization)
            k = blake2b_256_hash(int(s).to_bytes(length=4, byteorder="little") + pvm.mem[k_o:k_o + k_z])
        else:
            k = "∇"

        if bold_a != "∅" and k in bold_a.storage_items.has(k): #TODO: implement has & get
            bold_v = bold_a.storage_items.get(k)
        else:
            bold_v = "∅"

        if bold_v != "∅" and pvm.is_writable(pvm.mem, b_o, b_o + b_z):
            nr_bytes = min(b_z, len(bold_v))
            pvm.mem[b_o:b_o + nr_bytes] = np.frombuffer(bold_v[:nr_bytes], dtype=np.uint8)

        #TODO: hoe weten we dat de waarde voor storage_item misschien groter was dan max toegestaan (b_z), idem voor lookup
        if k != "∇" and pvm.is_writable(pvm.mem, b_o, b_o + b_z):
            if bold_v == "∅":
                pvm.reg[7] = HostCallResult.none.value
            else:
                pvm.reg[7] = len(bold_v)
        else:
            pvm.reg[7] = HostCallResult.oob.value

    def write(self, pvm, bold_s=None, s=None):
        """
        Writes/deletes a Service Preimage blob
        """
        pvm.gas -= 10

        k_o = pvm.reg[7]  # offset to read storage_item_key from memory
        k_z = pvm.reg[8]  # length to read storage_item_key from memory
        v_o = pvm.reg[9]   # offset to write storage_item_value from memory
        v_z = pvm.reg[10]  # length to write storage_item_value from memory

        if pvm.is_readable(pvm.mem, k_o, k_z):
            k = int(s).to_bytes(length=4, byteorder="little") +  pvm.mem[k_o:k_o + k_z]
        else:
            k = "∇"

        if pvm.is_readable(pvm.mem, v_o, v_z):
            bold_a = clone(bold_s)  # TODO: clone functie maken
            if v_z == 0:
                #TODO: s lijkt te worden gebruikt als index, maar bold_s is toch al een ServiceAccount object?
                bold_a.storage_items.delete(k)  # TODO: implement service_account.storage_items.delete
            else:
                bold_a.storage_items.set(k, pvm.mem[v_o:v_o + v_z])  # TODO: implement service_account.storage_items.set
        else:
            bold_a = "∇"

        if bold_s.storage_items.has(k): #TODO: implementeer storage_items.has
            #TODO: waarom wordt hier niet bold_a.storage_items.get(k) gebruikt??
            l = len(bold_s.storage_items.set(k)) #TODO: implementeer storage_items.set
        else:
            l = HostCallResult.none.value

        if k != "∇" and bold_a != "∇" and bold_a.threshold_balance <= bold_a.balance:
            pvm.reg[7] = l
            if v_z == 0:
                bold_s.storage_items.delete(k)  # TODO: implement service_account.storage_items.delete
            else:
                bold_s.storage_items.update(k, bold_a)  # TODO: implement service_account.storage_items.update
        elif bold_a.threshold_balance > bold_a.balance:
            pvm.reg[7] = HostCallResult.full.value
        else:
            pvm.reg[7] = HostCallResult.oob.value

    def info(self, pvm, s, bold_d:Dict[int, ServiceAccount]=None):
        """
        Writes ServiceAccount into PVM memory
        """
        pvm.gas -= 10
        w7 = pvm.reg[7]
        if w7 in (s, 2 ** 64 - 1):
            bold_t = bold_d.get_service_account(s)
        else:
            bold_t = bold_d.get_service_account(w7)

        o = pvm.reg[8]

        if bold_t:
            # TODO: add possibility to define which attributes and in which order to serialize
            m = bold_t.to_jam_bytes(
                ServiceAccount.code_hash,
                ServiceAccount.balance,
                ServiceAccount.threshold_balance,
                ServiceAccount.gas_limit_accumulate,
                ServiceAccount.gas_limit_on_transfer,
                ServiceAccount.footprint_storage_items,
                ServiceAccount.footprint_storage_bytes
            ).to_bytes()
        else:
            m = "∅"

        if m != "∅" and pvm.is_writable(pvm.mem, o, o + len(m)):
            pvm.mem[o:o + len(m)] = m

        if m != "∅" and pvm.is_writable(pvm.mem, o, o + len(m)):
            pvm.reg[7] = HostCallResult.ok.value
        elif m == "∅":
            pvm.reg[7] = HostCallResult.none.value
        else:
            pvm.reg[7] = HostCallResult.oob.value


    def invoke_from_pvm(self, pvm:PVM, host_call:op):
        """
        A generic entrypoint to invoke a hostcall from the PVM using the ecalli opcode (using register 7 as hostcall type)
        """

        #TODO: GENERIC handling of B.17 & B.19, B.21 (en in algemeen voor elke catagorie zoals general, accumulate en refine)
        #TODO: de afhandeling van niet genoeg gas verschilt per hostfunctie catagorie, B.18, B.20 en B.22 (general, accumulate en refine)
        match host_call:

            case op.gas.value:
                # ω'7 = ϱ
                pvm.reg[7] = pvm.gas

            case op.lookup.value:
                return self.lookup(pvm)

            case op.read.value:
                return self.read(pvm)

            case op.write.value:
                return self.write(pvm)

            case op.info.value:
                return self.info(pvm)

            case _:
                raise InvalidHostCall(f"Invalid invoke_from_pvm hostcall: {host_call}")
