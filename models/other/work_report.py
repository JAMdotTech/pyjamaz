from scalecodec.types import Struct, Vec, H256, Bytes
from models.other.refinement_context import RefinementContext
from models.other.work_package_specification import WorkPackageSpecification
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
        'work_package': WorkPackageSpecification(),
        'work_results': Vec(WorkResult()) #TODO Constant(I): MAXIMUM_WORK_ITEMS=4; Minimum size of list 1, maximum size of list is I(4) per GP-equation: 110; Needs to be more strict; How to solve?
    }

