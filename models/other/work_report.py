from scalecodec.types import Struct, Vec, H256, Bytes
from models.other.refinement_context import RefinementContext
from models.other.work_package import WorkPackage
from models.other.work_result import WorkResult


class WorkReport(Struct):
    #GP-equation: 130,110,W | "WORK_REPORT"->"(AUTHORIZERS_HASH,OUTPUT,REFINEMENT_CONTEXT,WORK_PACKAGE,RESULTS)"
    #GP-reference: - | SCALETYPE-DEFINITION: "AUTHORIZERS_HASH"->"H256"
    #GP-reference: - | SCALETYPE-DEFINITION: "OUTPUT"->"BYTES"
    #GP-reference: - | SCALETYPE-DEFINITION: "REFINEMENT_CONTEXT"-> refer to class RefinementContext for details.
    #GP-reference: - | SCALETYPE-DEFINITION: "WORK_PACKAGE"->  refer to class WorkPackage for details.
    #GP-reference: - | SCALETYPE-DEFINITION: "WORK_RESULTS"->"VEC<WORK_RESULT>" | "RESULT"-> refer to class WorkResult for details.
    arguments = {
        'authorizers_hash': H256,
        'output': Bytes,
        'refinement_context': RefinementContext(),
        'work_package': WorkPackage(),
        'work_results': Vec(WorkResult())
    }

