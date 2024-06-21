from scalecodec.base import ScaleBytes
from scalecodec.types import Struct, Vec, H256, VecType, Compact
from models.other.judgement_vote import JudgementVote


class JudgementVotes(Vec):
    #In deze class kunnen we data validatie afdwingen van een standaard vec
    #TODO Constant(V): VALIDATORS=1023; size of list is exactly (2*VALIDATORS)/3+1=683 Needs to be more strict. Possible Array(JudgementVote(),683); Round()|Floor()?
    def __init__(self):
        super().__init__()
        self.scale_type_cls = VecType
        self.type_def = JudgementVote()

    def decode(self, data: ScaleBytes) -> list:
        # deze functie dwingt validatie af

        # Decode length of Vec
        length = Compact().decode(data)
        if length != 683: # vervangen door constant
            raise ValueError('size of list should be 683')
        value = []

        for _ in range(0, length):
            obj = self.type_def.new()
            obj.decode(data)

            value.append(obj)

        return value

# TODO ENCODE VALIDATIE

class ExtrinsicJudgement(Struct):
    #GP-equation: 96,98,Ej,J | SCALETYPE-DEFINITION: "JUDGEMENT"->"(WORK_REPORT_HASH,VOTES)"
    #GP-reference: 96,99,H | SCALETYPE-DEFINITION: "WORK_REPORT_HASH"->"H256"
    #GP-reference: 96,97 | SCALETYPE-DEFINITION: "VOTES"->"VEC<VOTE>" | "VOTE"-> refer to class JudgementVote for details.
    arguments = {
        'work_report_hash': H256,
        'votes': JudgementVotes() #TODO Constant(V): VALIDATORS=1023; size of list is exactly (2*VALIDATORS)/3+1=683 Needs to be more strict. Possible Array(JudgementVote(),683); Round()|Floor()?
    }

