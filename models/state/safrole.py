from scalecodec.base import ScaleType
from scalecodec.types import Struct, Vec, Array, U8, Enum, H256

from models.block import Header
from models.common import Ticket, ValidatorKeys
from models.state.entropy import Entropy
from models.state.timeslot import Timeslot
from models.state.validator_pool import ValidatorPool
from models.state.validator_queue import ValidatorQueue


class SafroleObject(ScaleType):
    # GP-ref:19,56
    def state_transition(self, header: Header, timeslot: Timeslot, extrinsic_tickets: Vec, validator_queue: ValidatorQueue, validator_entropy: Entropy, validator_pool: ValidatorPool):
        # TODO: input 1: Safrole of current state (self)
        # TODO: input 2: Block.Header
        # TODO: input 3: Timeslot of current state
        # TODO: input 4: Block.Extrinsic.tickets
        # TODO: input 5: ValidatorQueue of current state
        # TODO: input 6: Entropy of transitioned state
        # TODO: input 7: ValidatorPool of transitioned state
        # TODO: output 1: self of transitioned state
        pass

   # TODO: with Arjan get/serialize/deserialize this subsection of the state
    def storage_serialize(self):
        # TODO: Generalize by introducing the StateKeyConstructor function (C) | # GP-ref:280
        # TODO: key: blake2b(0x04|4) # GP-ref: 281,(C4)
        # TODO: value: [define how to serialize] # GP-ref:281,(C4)
        pass

    def storage_persist(self):
        # TODO: insert/update_kvdb(key: blake2b(0x04|4), value: serialize(self))
        pass

    def storage_get(self):
        # TODO: set self = select_kvdb(key: blake2b(0x04|4))
        pass


class Safrole(Struct):
    # GP-ref:PSI,46
    scale_type_cls = SafroleObject
    arguments = {
        # TODO: Consider creating a class ValidatorKeySets [Vec(ValidatorKeys())]; simplifies strictness
        'validators': Vec(ValidatorKeys()), # GP-ref:GAMMA_k,50
        # TODO: Discuss with Arjan: fixed length Bytes-type
        'epoch_root': Array(U8,196608), # GP-ref:GAMMA_z,47
        # TODO: Consider creating a class Tickets [Vec(Ticket())]; simplifies strictness
        'slot_sealer_series': Enum(tickets=Vec(Ticket()), bs_keys=Vec(H256)), # GP-ref:GAMMA_s,48,49
        # TODO: Consider creating a class Tickets [Vec(Ticket())]; simplifies strictness
        'tickets': Vec(Ticket()) # GP-ref:GAMMA_a,48,49
    }
