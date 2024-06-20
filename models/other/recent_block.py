from scalecodec.types import Struct, H256, Vec, Option


class RecentBlock(Struct):
    #GP-equation: 79 | SCALETYPE-DEFINITION: "RECENT_BLOCK"->"(HEADER_HASH,ACCUMULATION_RESULTS,STATE_ROOT,WORK_REPORTS)"
    #GP-reference: 79,h | SCALETYPE-DEFINITION: "HEADER_HASH"->"H256"
    #GP-reference: 79,b | SCALETYPE-DEFINITION: "ACCUMULATION_RESULTS"->"OPTION<ACCUMULATION_RESULT>" | "ACCUMULATION_RESULT"->"H256"
    #GP-reference: 79,s | SCALETYPE-DEFINITION: "STATE_ROOT"->"H256"
    #GP-reference: 79,p | SCALETYPE-DEFINITION: "WORK_REPORTS"->"VEC<WORK_REPORT_HASH>" | "WORK_REPORT_HASH"->"H256"
    arguments = {
        'header_hash': H256,
        'accumulation_results': Vec(Option(H256)),
        'state_root': H256,
        'work_reports': Vec(H256)
    }
