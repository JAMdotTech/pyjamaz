from scalecodec.types import Struct, H256, Vec, Option


class RecentBlock(Struct):
    #GP-reference: BETA | SCALETYPE-DEFINITION: "RECENT_BLOCK"->"(HEADER_HASH,ACCUMULATION_RESULTS,STATE_ROOT,WORK_REPORTS)" | "HEADER_HASH"->"H256" | "ACCUMULATION_RESULTS"->"OPTION<ACCUMULATION_RESULT>" | "ACCUMULATION_RESULT"->"H256" | "STATE_ROOT"->"H256" | "WORK_REPORTS"->"VEC<WORK_REPORT_HASH>" | "WORK_REPORT_HASH"->"H256"
    arguments = {
        'header_hash': H256,
        'accumulation_results': Vec(Option(H256)),
        'state_root': H256,
        'work_reports': Vec(H256)
    }
