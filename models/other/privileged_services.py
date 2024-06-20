from scalecodec.types import Struct, U32


class PrivilegedServices(Struct):
    #GP-equation: 93 | SCALETYPE-DEFINITION: "PRIVILEGED_SERVICES"->"(MANAGER,MANAGER_AUTHORIZER_QUEUE,MANAGER_VALIDATOR_QUEUE)>"
    #GP-reference: 93,CHI-m,I.4.2 | SCALETYPE-DEFINITION: "MANAGER"->"U32"
    #GP-reference: 93,CHI-a,I.4.2 | SCALETYPE-DEFINITION: "MANAGER_AUTHORIZER_QUEUE"->"U32"
    #GP-reference: 93,CHI-v,I.4.2 | SCALETYPE-DEFINITION: "MANAGER_VALIDATOR_QUEUE"->"U32"
    arguments = {
        'service_empower': U32,
        'service_designate_authorizers': U32,
        'service_assign_validators': U32
    }

