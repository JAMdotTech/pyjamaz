from scalecodec.types import Struct, Vec, H256
from models.other.judgement_vote import JudgementVote


class ExtrinsicJudgement(Struct):
    #GP-equation: 96,98,Ej,J | SCALETYPE-DEFINITION: "JUDGEMENT"->"(WORK_REPORT_HASH,VOTES)"
    #GP-reference: 96,99,H | SCALETYPE-DEFINITION: "WORK_REPORT_HASH"->"H256"
    #GP-reference: 96,97 | SCALETYPE-DEFINITION: "VOTES"->"VEC<VOTE>" | "VOTE"-> refer to class JudgementVote for details.
    arguments = {
        'work_report_hash': H256,
        'votes': Vec(JudgementVote())
    }

