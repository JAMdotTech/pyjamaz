from scalecodec.base import ScaleType
from scalecodec.types import Struct, H256, U8, Bytes, Vec, U32, Option, I64, Enum, Bool


class TicketObject(ScaleType):
    def test(self):
        print('ja')


class Ticket(Struct):
    #GP-equation: 49,C | SCALETYPE-DEFINITION: "TICKET"->"(TICKET_ID,ENTRY_IDX)"
    #GP-reference: Y | SCALETYPE-DEFINITION: "TICKET_ID"->"H256"
    #GP-reference: r | SCALETYPE-DEFINITION: "ENTRY_IDX"->"U8"
    scale_type_cls = TicketObject
    arguments = {
        'ticket_id': H256,
        'entry_idx': U8 #TODO Constant(N): TICKET_ENTRIES=2; entry_idx=0|1 Needs to be more strict
    }


class RefinementContextObject(ScaleType):
    def test(self):
        print('ja')


class RefinementContext(Struct):
    #GP-equation: 112 | "REFINEMENT_CONTEXT"->"(ANCHOR_HEADER_HASH,ANCHOR_POSTERIOR_STATE_ROOT,POSTERIOR_BEEFY_ROOT,LOOKUP_ANCHOR_HEADER_HASH,LOOKUP_ANCHOR_TIMESLOT,OPTION<WORK_PACKAGE_HASH>)"
    #GP-reference: - | SCALETYPE-DEFINITION: "ANCHOR_HEADER_HASH"->"H256"
    #GP-equation: - | SCALETYPE-DEFINITION: "ANCHOR_POSTERIOR_STATE_ROOT"->"H256"
    #GP-equation: - | SCALETYPE-DEFINITION: "POSTERIOR_BEEFY_ROOT"->"H256"
    #GP-equation: - | SCALETYPE-DEFINITION: "LOOKUP_ANCHOR_HEADER_HASH"->"H256"
    #GP-equation: - | SCALETYPE-DEFINITION: "LOOKUP_ANCHOR_TIMESLOT"->"U32"
    #GP-equation: - | SCALETYPE-DEFINITION: "WORK_PACKAGE_HASH"->"H256"
    scale_type_cls = RefinementContextObject
    arguments = {
        'header_hash': H256,
        'posterior_state_root': H256,
        'posterior_beefy_root': H256,
        'lookup_header_hash': H256,
        'lookup_timeslot': U32,
        'work_package_hash': Option(H256) #TODO: simply optional; nothing special
    }


class WorkPackageSpecificationObject(ScaleType):
    def test(self):
        print('ja')


class WorkPackageSpecification(Struct):
    #GP-equation: 113,Ws | "WORK_PACKAGE_SPECIFICATION"->"(WORK_PACKAGE_HASH,WORK_PACKAGE_LENGTH,ERASURE_ROOT,SEGMENT_ROOT)"
    #GP-reference: - | SCALETYPE-DEFINITION: "WORK_PACKAGE_HASH"->"H256"
    #GP-reference: - | SCALETYPE-DEFINITION: "WORK_PACKAGE_LENGTH"->"U32"
    #GP-reference: - | SCALETYPE-DEFINITION: "ERASURE_ROOT"->"H256"
    #GP-reference: - | SCALETYPE-DEFINITION: "SEGMENT_ROOT"->"H256"
    scale_type_cls = WorkPackageSpecificationObject
    arguments = {
        'hash': H256,
        'length': U32, #Defined by GP-reference:I.1.1
        'erasure_root': H256,
        'segment_root': H256
    }


class WorkResultObject(ScaleType):
    def test(self):
        print('ja')


class WorkResult(Struct):
    #GP-equation: 114,115 | "RESULT"->"(SERVICE_IDX,CODE_HASH,PAYLOAD_HASH,GAS_PRIORITIZATION_RATIO,RESULT)"
    #GP-reference: - | SCALETYPE-DEFINITION: "SERVICE_IDX"->"U32"
    #GP-reference: - | SCALETYPE-DEFINITION: "CODE_HASH"->"H256"
    #GP-reference: - | SCALETYPE-DEFINITION: "PAYLOAD_HASH"->"H256"
    #GP-reference: - | SCALETYPE-DEFINITION: "GAS_PRIORITIZATION_RATIO"->"I64"
    #GP-reference: - | SCALETYPE-DEFINITION: "RESULT"->"ENUM<OUTPUT,OUT-OF-GAS,PANIC,BAD,BIG>" | "OUTPUT"->"BYTES" | "OUT-OF-GAS"->"BOOL" | "PANIC"->"BOOL" | "BAD"->"BOOL" | "BIG"->"BOOL"
    scale_type_cls = WorkResultObject
    arguments = {
        'service_idx': U32,
        'code_hash': H256,
        'payload_hash': H256,
        'gas_prioritization_ratio': I64,
        'result': Enum(output=Bytes,out_of_gas=Bool,panic=Bool,bad=Bool,big=Bool) #TODO: fixed values?!
    }


class WorkReportObject(ScaleType):
    def test(self):
        print('ja')


class WorkReport(Struct):
    #GP-equation: 130,110,W | "WORK_REPORT"->"(AUTHORIZERS_HASH,OUTPUT,REFINEMENT_CONTEXT,WORK_PACKAGE,RESULTS)"
    #GP-reference: - | SCALETYPE-DEFINITION: "AUTHORIZERS_HASH"->"H256"
    #GP-reference: - | SCALETYPE-DEFINITION: "OUTPUT"->"BYTES"
    #GP-reference: - | SCALETYPE-DEFINITION: "REFINEMENT_CONTEXT"-> refer to class RefinementContext for details.
    #GP-reference: - | SCALETYPE-DEFINITION: "WORK_PACKAGE"->  refer to class WorkPackage for details.
    #GP-reference: - | SCALETYPE-DEFINITION: "WORK_RESULTS"->"VEC<WORK_RESULT>" | "RESULT"-> refer to class WorkResult for details.
    scale_type_cls = WorkReportObject
    arguments = {
        'authorizers_hash': H256,
        'output': Bytes,
        'refinement_context': RefinementContext(),
        'work_package': WorkPackageSpecification(),
        'work_results': Vec(WorkResult()) #TODO Constant(I): MAXIMUM_WORK_ITEMS=4; Minimum size of list 1, maximum size of list is I(4) per GP-equation: 110; Needs to be more strict; How to solve?
    }

