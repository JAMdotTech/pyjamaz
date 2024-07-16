from scalecodec.base import ScaleType
from scalecodec.types import Struct, H256, U8, Bytes, Vec, U32, Option, I64, Enum, Bool, Array


class TicketObject(ScaleType):
    def test(self):
        print('ja')


class Ticket(Struct):
    # GP-equation:49,C
    scale_type_cls = TicketObject
    arguments = {
        'ticket_id': H256, # GP-reference:Y
        # TODO Constant(N): TICKET_ENTRIES=2; entry_idx=0|1 Needs to be more strict
        'entry_idx': U8 # GP-reference:r
    }


class RefinementContextObject(ScaleType):
    def test(self):
        print('ja')


class RefinementContext(Struct):
    # GP-equation:112
    scale_type_cls = RefinementContextObject
    arguments = {
        'header_hash': H256, # GP-reference:-
        'posterior_state_root': H256, # GP-reference:-
        'posterior_beefy_root': H256, # GP-reference:-
        'lookup_header_hash': H256, # GP-reference:-
        'lookup_timeslot': U32, # GP-reference:-
        # TODO: simply optional?; nothing special?
        'work_package_hash': Option(H256) # GP-reference:-
    }


class WorkPackageSpecificationObject(ScaleType):
    def test(self):
        print('ja')


class WorkPackageSpecification(Struct):
    # GP-equation:113,Ws
    scale_type_cls = WorkPackageSpecificationObject
    arguments = {
        'hash': H256, # GP-reference:-
        'length': U32, # GP-reference:I.1.1
        'erasure_root': H256, # GP-reference:-
        'segment_root': H256 # GP-reference:-
    }


class WorkResultObject(ScaleType):
    def test(self):
        print('ja')


class WorkResult(Struct):
    # GP-equation:114,115
    scale_type_cls = WorkResultObject
    arguments = {
        'service_idx': U32, # GP-reference:-
        'code_hash': H256, # GP-reference:-
        'payload_hash': H256, # GP-reference:-
        'gas_prioritization_ratio': I64, # GP-reference:-
        # TODO: check ENUM definition with fixed values?!
        'result': Enum(Ok=Bytes, Err=Enum(OutOfGas=None, Panic=None, Bad=None, Big=None)) # GP-reference:-
    }


class WorkReportObject(ScaleType):
    def test(self):
        print('ja')


class WorkReport(Struct):
    # GP-equation:130,110,W
    scale_type_cls = WorkReportObject
    arguments = {
        'authorizers_hash': H256, # GP-reference:-
        'output': Bytes, # GP-reference:-
        'refinement_context': RefinementContext(), # GP-reference:-
        'work_package': WorkPackageSpecification(), # GP-reference:-
        # TODO Constant(I): MAXIMUM_WORK_ITEMS=4; Minimum size of list 1, maximum size of list is I(4) per GP-equation: 110; Needs to be more strict; How to solve?
        'work_results': Vec(WorkResult()) # GP-reference:-
    }


class ValidatorKeysObject(ScaleType):
    def test(self):
        pass


class ValidatorKeys(Struct):
    # GP-ref:50,51,K
    scale_type_cls = ValidatorKeysObject
    arguments = {
        'bs_key': H256, # GP-ref:52,vb
        'ed25519_key': H256, # GP-ref:53,ve
        'bls_key': Array(U8,144), # GP-ref:54,vBLS
        'metadata': Array(U8,128) # GP-ref:55,vm
    }
