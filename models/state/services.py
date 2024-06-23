from scalecodec.base import ScaleType
from scalecodec.types import Struct, Bytes, Vec, U32, H256, U64, I64

from models.state.assurances import Assurances
from models.state.authorizer_queue import AuthorizerQueue
from models.state.privileged_services import PrivilegedServices
from models.state.timeslot import Timeslot
from models.state.validator_queue import ValidatorQueue


class ServiceAccountObject(ScaleType):
    # TODO: Assistance Arjan with Python Dict
    def get_storage_item(self):
        # TODO: input 1: storage_item_hash (H256)
        # TODO: output 1: ServiceAccount.storage_item[H256]
        pass

    # TODO: Assistance Arjan with Python Dict
    def get_preimage(self):
        # TODO: input 1: preimage_hash (H256)
        # TODO: output 1: ServiceAccount.preimage[H256]
        pass

    # TODO: Assistance Arjan with Python Dict
    def get_preimage_status(self):
        # TODO: input 1: preimage_hash (H256)
        # TODO: input 2: preimage_length (U32)
        # TODO: output 1: ServiceAccount.preimage_status[H256][U32]
        pass


class ServiceAccount(Struct):
    # GP-ref:87
    scale_type_cls = ServiceAccountObject
    arguments = {
        # TODO: Assistance Arjan with Python Dict
        # TODO: INDEX OF STORAGE_ITEM DICTIONARY: storage_item[HASH] = storage_item for storage_item_hash
        'storage_item_dictionary': Bytes, # GP-ref:87,?
        # TODO: Assistance Arjan with Python Dict
        # TODO: INDEX OF PREIMAGE DICTIONARY: preimage[HASH] = preimage for preimage_hash
        'preimage_dictionary': Bytes, # GP-ref:87,?
        # TODO: Assistance Arjan with Python Dict
        # TODO: INDEX OF PREIMAGE_STATUS DICTIONARY: preimage_status[HASH][LENGTH] = status for preimage_hash
        # TODO: upper bound to list size; size has a meaning
        'preimage_status_dictionary': Vec(U32), # GP-ref:87,?
        'code_hash': H256, # GP-ref:87,?
        'balance': U64, # GP-ref:87,?
        'gaslimit_accumulate': I64, # GP-ref:87,?
        'gaslimit_on_transfer': I64 # GP-ref:87,?
    }


class ServicesObject(ScaleType):
    # GP-ref:24
    def state_transition_preimages(self, extrinsic_preimages: Vec, timeslot: Timeslot):
        # TODO: input 1: Services of current state (self)
        # TODO: input 2: Block.Extrinsic.preimages
        # TODO: input 3: Timeslot of transitioned state
        # TODO: output 1: self of intermediate state
        pass

    # GP-ref:I.4.2
    # TODO: check inconsistency GP-ref:I.4.2 mentions function, whereas GP-ref:4.2.1 does not mention function
    # TODO: input: Unknown]
    def state_transition_accumulation(self):
        # TODO: output: unknown
        pass

    # GP-ref:28
    def state_transition(self, extrinsic_assurances: Vec, assurances: Assurances, privileged_services: PrivilegedServices, validator_queue: ValidatorQueue, authorizer_queue: AuthorizerQueue):
        # TODO: input 1: Services of intermediate state of GP-ref:24 (self)
        # TODO: input 2: Block.Extrinsic.assurances
        # TODO: input 3: Assurances of transitioned state of GP-ref:27
        # TODO: input 4: PrivilegedServices current state
        # TODO: input 5: ValidatorQueue of current state
        # TODO: input 6: AuthorizerQueue of current state
        # TODO: output 1: self of transitioned state
        pass

    # TODO: Assistance Arjan with Python Dict
    def get_service_account(self):
        # TODO: input 1: service_account_idx (U32)
        # TODO: output 1: services[U32]
        pass


class Services(Struct):
    # GP-ref:DELTA,86
    scale_type_cls = ServicesObject
    arguments = {
        # TODO: Assistance Arjan with Python Dict
        # TODO: INDEX OF SERVICE ACCOUNT services[i] = ServiceAccount is ServiceAccount of index 1
        'services': Vec(ServiceAccount())
    }
