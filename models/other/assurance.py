from scalecodec.types import Struct, Vec, H256, U32
from models.other.work_report import WorkReport


class Assurance(Struct):
    #GP-equation: 109 | SCALETYPE-DEFINITION: "ASSURANCE"->"(WORK_REPORT,GUARANTORS,TIMESLOT)"
    #GP-reference: 109,W | SCALETYPE-DEFINITION: "WORK_REPORT"-> refer to class WorkReport for details.
    #GP-reference: 109,g | SCALETYPE-DEFINITION: "GUARANTORS"->"VEC<GUARANTOR>"
    #GP-reference: 109,t | SCALETYPE-DEFINITION: "TIMESLOT"->"U32"

    arguments = {
        'work_report': WorkReport(),
        'guarantors': Vec(H256),
        'timeslot': U32
    }
