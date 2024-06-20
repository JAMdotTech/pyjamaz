from scalecodec.types import Struct, Vec, Option, U16, U32, H512
from models.other.work_report import WorkReport


class ExtrinsicGuarantee(Struct):
    #GP-equation: 130,Eg | SCALETYPE-DEFINITION: "GUARANTEE"->"(CORE_IDX,WORK_REPORT,TIMESLOT,CREDENTIAL)"
    #GP-reference: 130,c | SCALETYPE-DEFINITION: "CORE_IDX"->"U16"
    #GP-reference: 130,110,W | SCALETYPE-DEFINITION: "WORK_REPORT"-> refer to class WorkReport for details.
    #GP-reference: 130,t | SCALETYPE-DEFINITION: "TIMESLOT"->"U32"
    #GP-reference: 130,a | SCALETYPE-DEFINITION: "CREDENTIAL"->"VEC<OPTION<SIGNATURE>> | "SIGNATURE"->"H512"
    arguments = {
        'core_idx': U16,
        'work_report': WorkReport(),
        'timeslot': U32,
        'credential': Vec(Option(H512))
    }

