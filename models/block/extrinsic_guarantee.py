from scalecodec.types import Struct, Vec, Option, U32, H512
from models.other.work_report import WorkReport


class ExtrinsicGuarantee(Struct):
    #GP-equation: 130,Eg | SCALETYPE-DEFINITION: "GUARANTEE"->"(CORE_IDX,WORK_REPORT,TIMESLOT,CREDENTIAL)"
    #GP-reference: 130,c | SCALETYPE-DEFINITION: "CORE_IDX"->"U32" #Type implicit, but treated similar to validator_idx as derived from Hk in GP-equation 272
    #GP-reference: 130,110,W | SCALETYPE-DEFINITION: "WORK_REPORT"-> refer to class WorkReport for details.
    #GP-reference: 130,t | SCALETYPE-DEFINITION: "TIMESLOT"->"U32"
    #GP-reference: 130,a | SCALETYPE-DEFINITION: "CREDENTIAL"->"VEC<OPTION<SIGNATURE>> | "SIGNATURE"->"H512"
    arguments = {
        'core_idx': U32, #TODO: Type implicit, but treated similar to validator_idx as derived from Hk in GP-equation 272
        'work_report': WorkReport(),
        'timeslot': U32,
        'credential': Vec(Option(H512)) #TODO FixedValue (not a constant): 3 (assume core-size; validators/authorizer); Only 3rd value allowed None; Needs to be more strict
    }

