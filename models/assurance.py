from scalecodec.types import Struct, Vec, H256, U32

from models.work_report import WorkReport


class Assurance(Struct):
    #GP-reference: RHO | SCALETYPE-DEFINITION: "ASSURANCE"->"(WORK_REPORT,GUARANTORS,TIMESLOT)" | "WORK_REPORT"-> refer to class WorkReport for details. | "GUARANTORS"->"VEC<GUARANTOR>" | "TIMESLOT"->"U32"
    arguments = {
        'work_report': WorkReport(),
        'guarantors': Vec(H256),
        'timeslot': U32
    }
