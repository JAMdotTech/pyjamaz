from scalecodec.types import Struct, Vec, H256, Bytes
from models.other.refinement_context import RefinementContext
from models.other.work_package import WorkPackage
from models.other.work_result import WorkResult


class WorkReport(Struct):
    #GP-equation: 110 | "WORK_REPORT"->"(AUTHORIZERS_HASH,OUTPUT,REFINEMENT_CONTEXT,WORK_PACKAGE,RESULTS)" | "AUTHORIZERS_HASH"->"H256" | "OUTPUT"->"BLOB" | "REFINEMENT_CONTEXT"-> refer to class RefinementContext for details. | "WORK_PACKAGE"->  refer to class WorkPackage for details. | "WORK_RESULTS"->"VEC<WORK_RESULT>" | "RESULT"-> refer to class WorkResult for details.
    arguments = {
        'authorizers_hash': H256,
        'output': Bytes,
        'refinement_context': RefinementContext(),
        'work_package': WorkPackage(),
        'work_results': Vec(WorkResult())
    }

