from scalecodec.types import Struct, Vec, H256
from models.other.judgement_vote import JudgementVote


class ExtrinsicJudgement(Struct):
    #GP-equation: 96 | SCALETYPE-DEFINITION: "JUDGEMENT"->"(WORK_REPORT_HASH,VOTES)" | "WORK_REPORT_HASH"->"H256" | "VOTES"->"VEC<VOTE>" | "VOTE"-> refer to class JudgementVote for details.
    arguments = {
        'work_report_hash': H256,
        'votes': Vec(JudgementVote())
    }

