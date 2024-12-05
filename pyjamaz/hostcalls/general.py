import numpy as np

from pyjamaz.hashing import blake2b_256_hash

from .constants import HostCallGeneral as op, HostCallResult
from .exceptions import InvalidHostCall


# GP_B.6 General Functions
class GeneralFunctionsMixin:

    # TODO: add typings
    #ΩG
    def invoke_pvm(self, pvm, host_call, service_index=None):

        pvm.gas -= 10
        gas = pvm.gas

        service_db = self.app.get_service_db()

        match host_call:

            case op.gas.value:
                # ω'7 = ϱ
                pvm.reg[7] = gas

            case op.lookup.value:
                s = service_index   #TODO: service_index waar komt deze vandaan in het geval van ecalli invocation? niet? wordt dit ook welleens ergens anders vandaan aangeroepen?
                d = pvm.reg[7]
                a = s if s in (d, 2**64-1,) else d #service_dict[d]

                h_o = pvm.reg[8]    # offset to read image hash from pvm mem
                b_o = pvm.reg[9]    # offset to write image data to in pvm mem
                b_z = pvm.reg[10]   # max length to write in pvm mem

                # TODO: gebruik mem calls, check out of bounds
                if h_o+32 < len(pvm.mem):
                    preimage_hash = blake2b_256_hash(pvm.mem[h_o:h_o+32])
                    service = service_db.get(int.to_bytes(int(a), byteorder='little', length=1) + preimage_hash)
                else:
                    pvm.reg[7] = HostCallResult.oob.value
                    return

                #TODO: check of memory wel te beschrijven is -> blackboard_V
                if service is not None:
                    nr_bytes = min(b_z, len(service))
                    pvm.mem[b_o:b_o+nr_bytes] = np.frombuffer(service, dtype=np.uint8)
                    pvm.reg[7] = len(service)
                else:
                    pvm.reg[7] = HostCallResult.none.value

            case op.read.value:
                s = service_index                   #TODO: service_index waar komt deze vandaan in het geval van ecalli invocation?
                d = pvm.reg[7]                      #TODO: wat is d[w7] uit GP???
                a = None
                if s in (d, 2**64-1,):
                    a = s
                else:
                    a = d
                # elif d in service_dict:
                #     a = service_dict[d]

                k_o = pvm.reg[8]    # offset to read from
                k_z = pvm.reg[9]    # length to read
                b_o = pvm.reg[10]   # offset where to write to in pvm mem
                b_z = pvm.reg[11]   # max length to write in pvm mem

                # TODO: gebruik mem calls, check out of bounds
                if k_o < len(pvm.mem) >= (k_o + k_z):
                    preimage_hash = blake2b_256_hash(pvm.mem[k_o:k_o+k_z])
                    service = service_db.get(int.to_bytes(int(a), byteorder='little', length=1) + preimage_hash)
                else:
                    pvm.reg[7] = HostCallResult.oob.value
                    return

                #TODO: check of memory wel te beschrijven is
                if service is not None:
                    nr_bytes = min(b_z, len(service))
                    pvm.mem[b_o:b_o+nr_bytes] = np.frombuffer(service, dtype=np.uint8)
                    pvm.reg[7] = len(service)
                else:
                    pvm.reg[7] = HostCallResult.none.value

            case op.write.value:
                k_o = pvm.reg[7]
                k_z = pvm.reg[8]

                # TODO: gebruik mem calls, check out of bounds
                if k_o < len(pvm.mem) >= (k_o + k_z):
                    service_key = bytes(pvm.mem[k_o:k_o+k_z])
                    #service_key = blake2b_256_hash(k)
                else:
                    pvm.reg[7] = HostCallResult.oob.value
                    return

                # TODO: check of memory wel te beschrijven is
                if service_key is not None:

                    v_o = pvm.reg[9]
                    v_z = pvm.reg[10]

                    if v_o < len(pvm.mem) >= (v_o + v_z):
                        if v_z == 0:
                            service_db.delete(service_key)
                        else:
                            preimage_hash = pvm.mem[v_o:v_o+v_z]
                            service_db.put(service_key, bytes(preimage_hash))
                            #TODO: vereist ServiceAccount
                            #TODO:condities checken (FULL,s) & (OOB,s)
                            pvm.reg[7] = len(preimage_hash)
                    else:
                        pvm.reg[7] = HostCallResult.oob.value
                        return

                else:
                    pvm.reg[7] = HostCallResult.none.value

            case op.info.value:
                s = service_index
                d = pvm.reg[7]
                t = service_db.get(s) if d == 2 ** 64 - 1 else d
                o = pvm.reg[8]
                #TODO: vereist ServiceAccount

            case _:
                raise InvalidHostCall(f"Invalid hostcall: {host_call}")
