from scalecodec.base import ScaleType
from scalecodec.types import Struct, H256, Vec, Option

from models.block import Header


class RecentBlockObject(ScaleType):
    def test(self):
        pass


class RecentBlock(Struct):
    # GP-ref:79
    scale_type_cls = RecentBlockObject
    arguments = {
        'header_hash': H256, # GP-ref:79,h
        # TODO: check alternative for option (avoid option)
        'accumulation_results': Vec(Option(H256)), # GP-ref:79,b
        'state_root': H256, # GP-ref:79,s
        'work_reports': Vec(H256) # GP-ref:79,p
    }


class RecentBlocksObject(ScaleType):
    """
    Creates a new `RecentBlocks` object. RecentBlocks is an isolated subsection of State.
    GP-ref: 17
    """
    def state_transition_intermediate(self, header: Header):
        # TODO: input 1: RecentBlocks of current state (self)
        # TODO: input 2: Block.Header
        # TODO: output 1: self of intermediate state
        pass


    # GP-ref:18,80,81
    def state_transition(header: Header, judgements: Vec, self, i4: {}):
        # TODO: input 1: Block.Header
        # TODO: input 2: Block.Extrinsic.reports
        # TODO: input 3: StateRecentBlocks of intermediate state (result of GP-ref:17
        # TODO: input 4: 'C'-object to be determined Beefy related
        # TODO: output 1: self of transitioned state
        pass

    # TODO: with Arjan get/serialize/deserialize this subsection of the state
    def storage_serialize(self):
        # TODO: Generalize by introducing the StateKeyConstructor function (C) | # GP-ref:280
        # TODO: key: blake2b(0x03|3) # GP-ref:281,(C3)
        # TODO: value: [define how to serialize] # GP-ref:281,(C3) | [COMPLICATED]
        pass

    def storage_persist(self):
        # TODO: persist
        pass

    def storage_get(self):
        # TODO: key:blake2b(0x03|3)
        pass


class RecentBlocks(Struct):
    #GP-ref:BETA,79
    scale_type_cls = RecentBlocksObject
    arguments = {
        # TODO Constant(H): history=8; size of list is exactly recent_blocks=8 Needs to be more strict.
        'recent_blocks': Vec(RecentBlock())
    }
