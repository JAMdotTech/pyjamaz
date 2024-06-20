from scalecodec.types import Struct, H256, U32, Option


class RefinementContext(Struct):
    #GP-equation: 112 | "REFINEMENT_CONTEXT"->"(ANCHOR_HEADER_HASH,ANCHOR_POSTERIOR_STATE_ROOT,POSTERIOR_BEEFY_ROOT,LOOKUP_ANCHOR_HEADER_HASH,LOOKUP_ANCHOR_TIMESLOT,OPTION<WORK_PACKAGE_HASH>)"
    #GP-reference: - | SCALETYPE-DEFINITION: "ANCHOR_HEADER_HASH"->"H256"
    #GP-equation: - | SCALETYPE-DEFINITION: "ANCHOR_POSTERIOR_STATE_ROOT"->"H256"
    #GP-equation: - | SCALETYPE-DEFINITION: "POSTERIOR_BEEFY_ROOT"->"H256"
    #GP-equation: - | SCALETYPE-DEFINITION: "LOOKUP_ANCHOR_HEADER_HASH"->"H256"
    #GP-equation: - | SCALETYPE-DEFINITION: "LOOKUP_ANCHOR_TIMESLOT"->"U32"
    #GP-equation: - | SCALETYPE-DEFINITION: "WORK_PACKAGE_HASH"->"H256"
    arguments = {
        'header_hash': H256,
        'posterior_state_root': H256,
        'posterior_beefy_root': H256,
        'lookup_header_hash': H256,
        'lookup_timeslot': U32,
        'work_package_hash': Option(H256)
    }

