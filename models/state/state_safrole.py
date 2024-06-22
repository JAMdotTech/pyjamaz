from scalecodec.types import Struct, Vec, U8, Array, Enum, H256
from models.block import Header, Extrinsic
from models.common import Ticket
from models.other.validator_keys import ValidatorKeys
from models.state.state_entropy import StateEntropy
from models.state.state_timeslot import StateTimeslot
from models.state.state_validator_pool import StateValidatorPool
from models.state.state_validator_queue import StateValidatorQueue


class StateSafrole(Struct):
    #GP-equation: PSI,46 | SCALETYPE-DEFINITION: "SAFROLE"->"(VALIDATORS,EPOCH_ROOT,SLOT_SEALER_SERIES,TICKETS)>"
    #GP-reference: GAMMA_k,50 | SCALETYPE-DEFINITION: "VALIDATORS"->"VEC<VALIDATOR_KEYS>" | refer to class ValidatorKeys for details.
    #GP-reference: GAMMA_z,47 | SCALETYPE-DEFINITION: "EPOCH_ROOT"->"H1572864"
    #GP-reference: GAMMA_s,48,49 | SCALETYPE-DEFINITION: "SLOT_SEALER_SERIES"->"ENUM<TICKETS,BS_KEYS>"
    #GP-reference: GAMMA_a,48,49 | SCALETYPE-DEFINITION: "TICKETS"->"VEC<TICKET>" | "TICKET"-> refer to class Ticket for details
    arguments = {
        'validators': Vec(ValidatorKeys()),#TODO: Consider creating a class ValidatorKeySets [Vec(ValidatorKeys())]; simplifies strictness
        'epoch_root': Array(U8,196608),
        'slot_sealer_series': Enum(tickets=Vec(Ticket()), bs_keys=Vec(H256)), #TODO: Consider creating a class Tickets [Vec(Ticket())]; simplifies strictness
        'tickets': Vec(Ticket()) #TODO: Consider creating a class Tickets [Vec(Ticket())]; simplifies strictness
    }

    #GP-equation: 19,56
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: StateTimeslot of current state]
    #[TODO: input 3: Block.Extrinsic.tickets]
    #[TODO: input 4: StateSafrole of current state]
    #[TODO: input 5: StateValidatorQueue of current state]
    #[TODO: input 6: StateEntropy of transitioned state]
    #[TODO: input 7: StateValidatorPool of transitioned state]
    def state_transition(header: Header, state_timeslot: StateTimeslot, extrinsic: Extrinsic, self, state_validator_queue: StateValidatorQueue, state_validator_entropy: StateEntropy, state_validator_pool: StateValidatorPool):
        #[TODO: output 1: self of transitioned state]
        pass

    # GP-equation: 281,(C4)
    def storage_serialize(self):
        #TODO: serialize(self.1, self.2, IF_ELSE_BOOL, self.3, self.4)
        #TODO ATTENTION: ordering is required per GP-equation: 281
        pass

    #TODO: Generalize by introducing the StateKeyConstructor function (C) | GP-reference 280
    def storage_persist(self):
        #TODO: insert/update_kvdb(key:blake2b(0x04|4),value:serialize(self.1, self.2, IF_ELSE_BOOL, self.3, self.4))
        pass

    def storage_get(self):
        #TODO: set self = select_kvdb(key:blake2b(0x04|4))
        pass

