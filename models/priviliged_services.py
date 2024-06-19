from scalecodec.types import Struct, U32


class PriviligedServices(Struct):
    #GP-reference: CHI | SCALETYPE-DEFINITION: "PRIVILIGED_SERVICES"->"(MANAGER,MANAGER_AUTHORIZER_QUEUE,MANAGER_VALIDATOR_QUEUE)>" | "MANAGER"->"U32" | "MANAGER_AUTHORIZER_QUEUE"->"U32" | "MANAGER_VALIDATOR_QUEUE"->"U32"
    #TODO: MANAGER: Empower-Service (GP-I.4.2)
    #TODO: MANAGER_AUTHORIZER_QUEUE: Designate-Service (GP-I.4.2)
    #TODO: MANAGER_VALIDATOR_QUEUE: Assign-Service (GP-I.4.2)
    arguments = {
        'service_empower': U32,
        'service_designate': U32,
        'service_assign': U32
    }

