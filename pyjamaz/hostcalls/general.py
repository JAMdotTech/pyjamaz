from pyjamaz.hashing import blake2b_256_hash

from .constants import HostCallGeneral as op, HostCallResult
from .exceptions import InvalidHostCall


# GP_B.6 General Functions
class GeneralFunctionsMixin:

    # TODO: add typings
    def invoke_pvm(self, pvm, host_call, service_index=None):

        pvm.gas -= 10

        service_dict = {}  # TODO!!!! read from DB

        match host_call:

            case op.gas.value:
                pvm.reg[7] = pvm.gas

            case op.lookup.value:
                s = service_index                   #TODO: service_index waar komt deze vandaan in het geval van ecalli invocation?
                d = pvm.reg[7]                      #TODO: wat is d[w7] uit GP???
                a = s if s in (d, 2**64-1,) else service_dict[d]

                h_o = pvm.reg[8]
                b_o = pvm.reg[9]
                b_z = pvm.reg[10]

                # TODO: gebruik mem calls, check out of bounds
                if h_o+32 <= len(pvm.mem):
                    preimage_hash = blake2b_256_hash(pvm.mem[h_o:h_o+32])
                    #TODO: alle db lookups met byte strings zoals b'preimage:' consts maken!!!!!
                    preimage = self.service_db.get(b'preimage:' + int.to_bytes(a, byteorder='little', length=1) + preimage_hash)
                else:
                    pvm.reg[7] = HostCallResult.oob.value
                    return

                #TODO: check of memory wel te beschrijven is
                if preimage is not None:
                    nr_bytes = min(b_z, len(preimage))
                    #TODO: append bytes?
                    pvm.mem[b_o:nr_bytes] = preimage
                    pvm.reg[7] = len(preimage)
                else:
                    pvm.reg[7] = HostCallResult.none.value

            case op.read.value:
                service_dict = {}                   #TODO!!!!
                s = service_index                   #TODO: service_index waar komt deze vandaan in het geval van ecalli invocation?
                d = pvm.reg[7]                      #TODO: wat is d[w7] uit GP???
                a = None
                if s in (d, 2**64-1,):
                    a = s
                elif d in service_dict:
                    a = service_dict[d]

                k_o = pvm.reg[8]
                k_z = pvm.reg[9]
                b_o = pvm.reg[10]
                b_z = pvm.reg[11]

                # TODO: gebruik mem calls, check out of bounds
                if k_o < len(pvm.mem) >= k_z:
                    preimage_hash = blake2b_256_hash(pvm.mem[k_o:k_z])
                    preimage = self.service_db.get(b'preimage:' + int.to_bytes(a, byteorder='little', length=1) + preimage_hash)
                else:
                    pvm.reg[7] = HostCallResult.oob.value
                    return

                #TODO: check of memory wel te beschrijven is
                if preimage is not None:
                    nr_bytes = min(b_z, len(preimage))
                    #TODO: append bytes?
                    pvm.mem[b_o:nr_bytes] = preimage
                    pvm.reg[7] = len(preimage)
                else:
                    pvm.reg[7] = HostCallResult.none.value

            case op.write.value:
                k_o = pvm.reg[8]
                k_z = pvm.reg[9]

                # TODO: gebruik mem calls, check out of bounds
                if k_o < len(pvm.mem) >= k_z:
                    preimage_hash = blake2b_256_hash(pvm.mem[k_o:k_z])
                    preimage = self.service_db.get(
                        b'preimage:' + preimage_hash
                    )
                else:
                    pvm.reg[7] = HostCallResult.oob.value
                    return

                # TODO: check of memory wel te beschrijven is
                if preimage is not None:

                    v_o = pvm.reg[10]
                    v_z = pvm.reg[11]

                    #TODO
                else:
                    pvm.reg[7] = HostCallResult.none.value

            case op.info.value:
                s = service_index  # TODO: service_index waar komt deze vandaan in het geval van ecalli invocation?
                d = pvm.reg[7]
                t = service_dict[s] if d == 2 ** 64 - 1 else service_dict[d]
                o = pvm.reg[8]
                #TODO: m = ??????

            case _:
                raise InvalidHostCall(f"Invalid hostcall: {host_call}")
