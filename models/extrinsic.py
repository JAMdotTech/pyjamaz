from scalecodec.types import Struct, Vec
from models.extrinsic_ticket import ExtrinsicTicket
from models.extrinsic_judgement import ExtrinsicJudgement
from models.extrinsic_preimage import ExtrinsicPreimage
from models.extrinsic_assurance import ExtrinsicAssurance
from models.extrinsic_guarantee import ExtrinsicGuarantee


class Extrinsic(Struct):
    #GP-equation: 71 | SCALETYPE-DEFINITION: "TICKETS"->"VEC<TICKET>" | refer to class ExtrinsicTicket for details.
    #GP-equation: 96 | SCALETYPE-DEFINITION: "JUDGEMENTS"->"VEC<JUDGEMENT>" | refer to class ExtrinsicJudgement for details.
    #GP-equation: 148 | SCALETYPE-DEFINITION: "PREIMAGES"->"VEC<PREIMAGE>" | refer to class ExtrinsicPreimage for details.
    #GP-equation: 116-120 | SCALETYPE-DEFINITION: "ASSURANCES"->"VEC<ASSURANCE>" | refer to class ExtrinsicAssurance for details.
    #GP-equation: 130 | SCALETYPE-DEFINITION: "GUARANTEES"->"VEC<GUARANTEE>" | refer to class ExtrinsicGuarantee for details.
    arguments = {
        'tickets': Vec(ExtrinsicTicket()),
        'judgements': Vec(ExtrinsicJudgement()),
        'preimages': Vec(ExtrinsicPreimage()),
        'assurances': Vec(ExtrinsicAssurance()),
        'guarantees': Vec(ExtrinsicGuarantee())
    }

    #GP-equation: 14 | SCALETYPE-DEFINITION: "EXTRINSIC"->"(TICKETS,JUDGEMENTS,PREIMAGES,ASSURANCES,GUARANTEES)"
    #DEFINE FUNCTION THAT SERIALIZES EXTRINSIC(DATA)
    #DEFINE FUNCTION THAT UNSERIALIZES EXTRINSIC(DATA)

    #GP-equation: 39
    #DEFINE FUNCTION THAT HASHES EXTRINSIC(DATA)
