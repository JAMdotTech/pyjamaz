from scalecodec.types import Struct, H256, U32


class WorkPackage(Struct):
    #GP-equation: 113 | "WORK_PACKAGE"->"(WORK_PACKAGE_HASH,WORK_PACKAGE_LENGTH,ERASURE_ROOT,SEGMENT_ROOT)" | "WORK_PACKAGE_HASH"->"H256" | "WORK_PACKAGE_LENGTH"->"U32" | "ERASURE_ROOT"->"H256" | "SEGMENT_ROOT"->"H256"
    arguments = {
        'hash': H256,
        'length': U32,
        'erasure_root': H256,
        'segment_root': H256
    }

