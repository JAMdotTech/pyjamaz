from typing import Dict

import numpy as np

from pyjamaz.hashing import blake2b_256_hash

from .constants import HostCallGeneral as op, HostCallResult
from .exceptions import InvalidHostCall
from ..models.state import ServiceAccount
from ..pvm import PVM


# TODO: we slaan nu direct resultaat op in bijv pvm registers... wellicht dit eerst in een intermediate state opslaan?
# GP_B.6 General Functions
class GeneralFunctionsMixin:

    # TODO: #ΩG
    # bold_s: Service, s: ServiceIndex, d:ServiceLookup
    #(ϱ:Gas, ω:Pvm_registers, µ:pvm_memory, bold_s:Service, s:ServiceIndex, d:ServiceDict) K:element of???  H:scale encoded?????
    def lookup(self, pvm:PVM, bold_s:ServiceAccount=None, s:int=None, d:Dict[int, ServiceAccount]=None):
        """
        Puts a Service Preimage blob into PVM memory
        """
        pvm.gas -= 10
        w7 = pvm.reg[7]
        if w7 in (s, 2 ** 64 - 1):
            bold_a = bold_s
        else:
            bold_a = d[w7]

        h_o = pvm.reg[8]  # offset to read image hash from pvm mem
        b_o = pvm.reg[9]  # offset to write image data to in pvm mem
        b_z = pvm.reg[10]  # max length to write in pvm mem

        if pvm.is_readable(pvm.mem, h_o, h_o + 32):
            h = blake2b_256_hash(pvm.mem[h_o:h_o + 32]) # create the preimage hash
        else:
            h = "∇"

        if bold_a and h in bold_a.preimages:
            bold_v = bold_a.preimages.get(h)    #TODO: service_account.preimages.get implementeren!
        else:
            bold_v = "∅"

        if bold_v != "∅" and pvm.is_writable(pvm.mem, b_o, b_o + b_z):  #TODO: waarom blackboard_Z en niet blackboard_N? deze range mag volgens GP negatief zijn?
            pvm.mem[b_o:b_o + b_z] = np.frombuffer(bold_v, dtype=np.uint8)

        if h != "∇" and pvm.is_writable(pvm.mem, b_o, b_o + b_z):
            if bold_v == "∅":
                pvm.reg[7] = HostCallResult.none.value
            else:
                pvm.reg[7] = len(bold_v)
        else:
            pvm.reg[7] = HostCallResult.oob.value

    def read(self, pvm:PVM, bold_s:ServiceAccount=None, s:int=None, d:Dict[int, ServiceAccount]=None):
        """
        Puts a Service StorageItem blob into PVM memory
        """
        pvm.gas -= 10

        w7 = pvm.reg[7]
        if w7 in (s, 2 ** 64 - 1):
            bold_a = bold_s
        elif w7 in d:
            bold_a = d[w7]
        else:
            bold_a = "∅"

        k_o = pvm.reg[8]  # offset to read from
        k_z = pvm.reg[9]  # length to read
        b_o = pvm.reg[10]  # offset where to write to in pvm mem
        b_z = pvm.reg[11]  # max length to write in pvm mem

        if pvm.is_readable(pvm.mem, k_o, k_o + k_z):
            k = blake2b_256_hash(pvm.mem[k_o:k_o + k_z])    # Note: k == storage item key
        else:
            k = "∇"

        if bold_a != "∅" and k in bold_a.services:
            bold_v = bold_a.services[s].storage_items.get(k)
        else:
            bold_v = "∅"

        if bold_v != "∅" and pvm.is_writable(pvm.mem, b_o, b_o + b_z):
            nr_bytes = min(b_z, len(bold_v))
            pvm.mem[b_o:b_o + nr_bytes] = np.frombuffer(bold_v, dtype=np.uint8)

        if k != "∇" and pvm.is_writable(pvm.mem, b_o, b_o + b_z):
            if bold_v == "∅":
                pvm.reg[7] = HostCallResult.none.value
            else:
                pvm.reg[7] = len(bold_v)
        else:
            pvm.reg[7] = HostCallResult.oob.value

    def write(self, pvm, bold_s=None, s=None):
        pvm.gas -= 10

        k_o = pvm.reg[7]  # offset in mem
        k_z = pvm.reg[8]  # length to read
        v_o = pvm.reg[9]
        v_z = pvm.reg[10]

        if pvm.is_readable(pvm.mem, k_o, k_z):
            k = pvm.mem[k_o:k_o + k_z]
        else:
            k = "∇"

        if pvm.is_readable(pvm.mem, v_o, v_z):
            if v_z == 0:
                #TODO: s lijkt te worden gebruikt als index, maar bold_s is toch al een ServiceAccount object?
                bold_a = bold_s.storage_items.get(k)
                #bold_s.storage_items.delete(k)  # TODO: implement service_account.storage_items.delete
            else:
                bold_a = pvm.mem[v_o:v_o + v_z]
                #bold_s.storage_items.update(k, bold_a)  # TODO: implement service_account.storage_items.update
        else:
            bold_a = "∇"

        if k in bold_s.storage_items:
            # TODO: wat is het verschil tussen bold_a[s] en bold_s[s]??????
            #bold_s.storage_items.get(s) == bold_a
            l = len(bold_a)
        else:
            l = HostCallResult.none.value

        if k != "∇" and bold_a != "∇" and bold_a.threshold < bold_a.balance:
            pvm.reg[7] = l
            if v_z == 0:
                bold_s.storage_items.delete(k)  # TODO: implement service_account.storage_items.delete
            else:
                bold_s.storage_items.update(k, bold_a)  # TODO: implement service_account.storage_items.update
        elif bold_a.threshold > bold_a.balance:
            pvm.reg[7] = HostCallResult.full.value
        else:
            pvm.reg[7] = HostCallResult.oob.value

    def info(self, pvm, bold_s=None, s=None, d=None):
        """
        Reads ServiceAccount info into PVM memory
        """
        pvm.gas -= 10
        w7 = pvm.reg[7]
        if w7 in (s, 2 ** 64 - 1):
            bold_t = bold_s
        else:
            bold_t = d[w7]

        o = pvm.reg[8]

        if bold_t:
            # TODO: bold_t.t -> threshold balance moet nog komen (zit nog niet in model)
            # TODO: m = scale_encode(bold_t.c, bold_t.b, bold_t.t, bold_t.g, bold_t.m, bold_t.l, bold_t.i)
            m = []
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
