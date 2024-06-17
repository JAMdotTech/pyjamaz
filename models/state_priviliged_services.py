from scalecodec.types import Struct, Tuple, U32


class StatePriviligedServices(Struct):
    #GP-reference: CHI | SCALETYPE-DEFINITION: "PRIVILIGED_SERVICES"->"(MANAGER,MANAGER_AUTHORIZER_QUEUE,MANAGER_VALIDATOR_QUEUE)>" | "MANAGER"->"U32" | "MANAGER_AUTHORIZER_QUEUE"->"U32" | "MANAGER_VALIDATOR_QUEUE"->"U32"
    arguments = {
        'priviliged_services': Tuple(U32,U32,U32)
    }

    #graypaper-equation: 28
    #[TODO: input 1: Block.Extrinsic.assurances]
    #[TODO: input 2: State.assurances of transitioned state of graypaper-equation: 27]
    #[TODO: input 3: State.services of intermediate state of graypaper-equation: 24]
    #[TODO: input 4: State.priviliged_services current state]
    #[TODO: input 5: State.enqueued_validators of current state]
    #[TODO: input 6: State.authorizers_queue of current state]
    def state_transition(i1: {}, i2: {}, i3: {}, i4: {}, i5: {}, i6: {}):
        #[TODO: output 2: self transitioned state]
        pass

