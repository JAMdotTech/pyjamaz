from scalecodec.types import Struct, Tuple, Vec, H256, U8
from models.header import Header
from models.validator_keys import ValidatorKeys


class StateSafrole(Struct):
    #GP-reference: PSI | SCALETYPE-DEFINITION: "SAFROLE"->"(VALIDATORS,EPOCH_ROOT,SLOT_SEALER_SERIES,TICKETS)>" | "VALIDATORS"->"VEC<VALIDATOR_KEYS>" | refer to class ValidatorKeys for details. | "EPOCH_ROOT"->"H1572864"  | "SLOT_SEALER_SERIES"->"ENUM<TICKETS,BS_KEYS>" | "TICKETS"->"VEC<TICKET>" | "TICKET"->"(TICKET_ID,ENTRY_IDX)" | "TICKET_ID"->"H256" | "ENTRY_IDX"->"U8"
    #TODO: "EPOCH_ROOT"->"H1572864" (new type large hash)
    #TODO: "SLOT_SEALER_SERIES"->"ENUM" (new type XOR)
    arguments = {
        'safrole': Tuple(Vec(ValidatorKeys()),H256,Enum(Vec(H256,U8),H256),Vec(H256,U8))
    }

    #graypaper-equation: 19
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: Timeslot of current state]
    #[TODO: input 3: Block.Extrinsic.tickets]
    #[TODO: input 4: State.safrole of current state]
    #[TODO: input 5: State.enqueued_validators of current state]
    #[TODO: input 6: State.entropy of transitioned state]
    #[TODO: input 7: State.validators of transitioned state]
    def state_transition(header: Header, i2: {}, i3: {}, i4: {}, i5: {}, i6: {}, i7: {}):
        #[TODO: output 1: self of transitioned state]
        pass

