class Extrinsic:
    #graypaper-equation: 14
    def __init__(self):
        # graypaper-equation: 71
        #SCALETYPE-DEFINITION: "TICKETS"->"VEC<TICKET>"
        #ENCODED: 'HOEGINGDATOOKALWEER'
        #PYTHON: []
        #DECODED-JSON: []
        self.tickets = []

        # graypaper-equation: 96
        #SCALETYPE-DEFINITION: "JUDGEMENTS"->"VEC<JUDGEMENT>" | type: "JUDGEMENT" specified in extrinsic_judgement.py
        #ENCODED: 'HOEGINGDATOOKALWEER'
        #PYTHON: []
        #DECODED-JSON: []
        self.judgements = []

        # graypaper-equation: 148
        #SCALETYPE-DEFINITION: "PREIMAGES"->"VEC<PREIMAGE>" | type: "PREIMAGE" specified in extrinsic_preimage.py
        #ENCODED: 'HOEGINGDATOOKALWEER'
        #PYTHON: []
        #DECODED-JSON: []
        self.preimages = []

        # graypaper-equation: 116-120
        #SCALETYPE-DEFINITION: "ASSURANCES"->"VEC<ASSURANCE>" | type: "ASSURANCE" specified in extrinsic_assurance.py
        #ENCODED: 'HOEGINGDATOOKALWEER'
        #PYTHON: []
        #DECODED-JSON: []
        self.assurances = []

        # graypaper-equation: 130
        #SCALETYPE-DEFINITION: "GUARANTEES"->"VEC<GUARANTEE>" | type: "GUARANTEE" specified in extrinsic_guarantee.py
        #ENCODED: 'HOEGINGDATOOKALWEER'
        #PYTHON: []
        #DECODED-JSON: []
        self.guarantees = []

        # graypaper-equation: 14
        #DEFINE FUNCTION THAT OUTPUTS SERIALIZED EXTRINSIC(DATA)
        #SCALETYPE-DEFINITION: "EXTRINSIC"->"(TICKETS,JUDGEMENTS,PREIMAGES,AVAILABILITY,REPORTS)"
        #ENCODED: 0x0000000000
        #PYTHON: [TODO]
        #DECODED-JSON: { "tickets": [],
        # "judgements": [],
        # "preimages": [],
        # "availability": [],
        # "reports": []
        # }

        # graypaper-equation: 14
        # DEFINE FUNCTION THAT UNSERIALIZES EXTRINSIC(DATA)

        # graypaper-equation: 39
        # DEFINE FUNCTION THAT HASHES EXTRINSIC(DATA)

        # graypaper-equation: 39
        # DEFINE FUNCTION THAT VERIFIES HASH OF EXTRINSIC(DATA)


