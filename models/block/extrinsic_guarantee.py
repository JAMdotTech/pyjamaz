from scalecodec.types import Struct, Vec, Option, U16, U32, H512
from models.other.work_report import WorkReport


class ExtrinsicGuarantee(Struct):
    #GP-equation: 130 | SCALETYPE-DEFINITION: "GUARANTEE"->"(CORE_IDX,WORK_REPORT,TIMESLOT,CREDENTIAL)" | "CORE_IDX"->"U16" | "WORK_REPORT"-> refer to class WorkReport for details. | "TIMESLOT"->"U32" | "CREDENTIAL"->"VEC<OPTION<SIGNATURE>> | "SIGNATURE"->"H512"
    arguments = {
        'core_idx': U16,
        'work_report': WorkReport(),
        'timeslot': U32,
        'credential': Vec(Option(H512))
    }

