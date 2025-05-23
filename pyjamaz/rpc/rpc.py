from jamcodec.base import JamBytes

import pyjamaz.graypaper_constants as gp_const
from pyjamaz.app import PyjamazApp
from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.models.block import Preimage
from pyjamaz.models.common import WorkPackage

#TODO: enum
RPC_TYPE_REQUEST = 1
RPC_TYPE_SUBSCRIBE = 2
RPC_TYPE_UNSUBSCRIBE = 3


def rpcParameters(app, params):
    return {
        "V1": {
            "deposit_per_account": gp_const.MINIMUM_BALANCE_SERVICE,
            "deposit_per_item": gp_const.MINIMUM_BALANCE_ITEM,
            "deposit_per_byte": gp_const.MINIMUM_BALANCE_OCTET,
            "min_turnaround_period": gp_const.PREIMAGE_EXPUNGE_TIMESLOTS,
            "epoch_period": gp_const.EPOCH_TIMESLOTS,
            "max_accumulate_gas": gp_const.GAS_ACCUMULATION,
            "max_is_authorized_gas": gp_const.GAS_INVOKE,
            "max_refine_gas": gp_const.GAS_REFINE,
            "block_gas_limit": gp_const.GAS_TOTAL,
            "recent_block_count": gp_const.HISTORY,
            "max_work_items": gp_const.MAXIMUM_WORK_ITEMS,
            "max_dependencies": gp_const.MAXIMUM_DEPENDENCIES_WORK_REPORT,
            "max_tickets_per_block": gp_const.MAXIMUM_EXTRINSIC_TICKETS,
            "max_lookup_anchor_age": gp_const.MAXIMUM_AGE_LOOKUP_ANCHOR,
            "tickets_attempts_number": gp_const.TICKET_ENTRIES,
            "auth_window": gp_const.MAXIMIM_AUTHORIZATION_POOL_ITEMS,
            "auth_queue_len": gp_const.MAXIMUM_AUTHORIZATION_QUEUE_ITEMS,
            "rotation_period": gp_const.ROTATION_PERIOD_CORE,
            "max_extrinsics": gp_const.MAXIMUM_NUMBER_EXTRINSICS_WORK_PACKAGE,
            "availability_timeout": gp_const.UNAVAILABLE_WORK_REPLACEMENT_PERIOD,
            "val_count": gp_const.VALIDATOR_COUNT,
            "max_input": gp_const.MAXIMUM_SIZE_WORK_PACKAGE,
            # "max_refine_code_size": gp_const.MAXIMUM_SIZE_SERVICE_CODE,
            "max_service_code_size": gp_const.MAXIMUM_SIZE_SERVICE_CODE,
            "basic_piece_len": gp_const.SIZE_ERASURE_CODED_PIECES,
            "max_imports": gp_const.MAXIMUM_NUMBER_IMPORTS_WORK_PACKAGE,
            "max_authorizer_code_size": gp_const.MAXIMUM_SIZE_SERVICE_CODE,
            # "max_is_authorized_code_size": gp_const.MAXIMUM_SIZE_SERVICE_CODE,
            # TODO not yet defined in JIP2
            "max_exports": gp_const.MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE,
            "max_refine_memory": 2**16,
            "max_is_authorized_memory": 2**16,
            "slot_period_ns": gp_const.SLOT_PERIOD * 1000000000,
            "epoch_tail_start": gp_const.TICKET_SUBMISSION_END_SLOT,
        }
    }


def rpcBestBlock(app, params):
    return [
        list(app.retrieve_block_hash(app.state.timeslot.number)),
        app.state.timeslot.number
    ]

def rpcFinalizedBlock(app, params):
    return [
        list(app.retrieve_block_hash(app.state.timeslot.number)),
        app.state.timeslot.number
    ]

def rpcServiceData(app, params):
    try:
        service = app.state.services.retrieve_service_account(params[1])
        return list(service.to_serialized_bytes())
    except StateKeyNoResult:
        return None


def rpcListServices(app, params):
    try:
        #TODO:
        #service = app.state.services.retrieve_service_accounts()
        return [0]
    except StateKeyNoResult:
        return None


def rpcServicePreimage(app, params):
    try:
        return list(app.state.services.retrieve_preimage(params[1], bytes(params[2])))
    except StateKeyNoResult:
        return None


def rpcStateRoot(app, params):
    return list(app.state_trie_root)


def rpcBeefyRoot(app: PyjamazApp, params):
    return list(app.get_beefy_root())


def rpcSubmitWorkPackage(app: PyjamazApp, params):
    #TODO: should assign to a specific core
    ex = [bytes(x) for x in params[2]]
    wp = WorkPackage.from_jam_bytes(JamBytes(bytes(params[1])))
    app.add_work_package(wp, ex)


def rpcSubmitPreimage(app: PyjamazApp, params):
    preimage_blob = bytes(params[1])
    #block_hash = bytes(params[2])
    pr = Preimage(requester=params[0], blob=preimage_blob)
    app.extrinsic.add_preimage(pr)


def rpcServiceRequest(app: PyjamazApp, params):
    try:
        return app.state.services.retrieve_preimage_availability(params[1], bytes(params[2]), params[3])
    except StateKeyNoResult:
        return None

def subscribeServiceRequest(app: PyjamazApp, params):
    try:
        return app.state.services.retrieve_preimage_availability(params[0], bytes(params[1]), params[2])
    except StateKeyNoResult:
        return None


rpc_requests = {
    "parameters": rpcParameters,
    "bestBlock": rpcBestBlock,
    "finalizedBlock": rpcFinalizedBlock,
    "stateRoot": rpcStateRoot,
    "beefyRoot": rpcBeefyRoot,
    "serviceData": rpcServiceData,
    "listServices": rpcListServices,
    "servicePreimage": rpcServicePreimage,
    "submitWorkPackage": rpcSubmitWorkPackage,
    "submitPreimage": rpcSubmitPreimage,
    "serviceRequest": rpcServiceRequest,
    "subscribeServiceRequest": subscribeServiceRequest,
}
