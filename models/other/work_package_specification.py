from scalecodec.types import Struct, H256, U32


class WorkPackageSpecification(Struct):
    #GP-equation: 113,Ws | "WORK_PACKAGE_SPECIFICATION"->"(WORK_PACKAGE_HASH,WORK_PACKAGE_LENGTH,ERASURE_ROOT,SEGMENT_ROOT)"
    #GP-reference: - | SCALETYPE-DEFINITION: "WORK_PACKAGE_HASH"->"H256"
    #GP-reference: - | SCALETYPE-DEFINITION: "WORK_PACKAGE_LENGTH"->"U32"
    #GP-reference: - | SCALETYPE-DEFINITION: "ERASURE_ROOT"->"H256"
    #GP-reference: - | SCALETYPE-DEFINITION: "SEGMENT_ROOT"->"H256"
    arguments = {
        'hash': H256,
        'length': U32, #Defined by GP-reference:I.1.1
        'erasure_root': H256,
        'segment_root': H256
    }

