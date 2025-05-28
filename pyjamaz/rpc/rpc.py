import json
import logging
import uuid

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


RPC_ERROR = {
    "UNKNOWN_HEADER_HASH": {"code": 3000, "msg": "The given header hash is not known"},
    "UNKNOWN_MESSAGE_TYPE": {"code": -32601, "msg": "Method not found"},
    "INVALID_PARAMS": {"code": -32602, "msg": "Invalid params"},
    "PARSE_ERROR": {"code": -32700, "msg": "Parse error"},
}


class RPCCallException(Exception):
    def __init__(self, reason, req_id, rpc_call, data):
        self.reason = reason
        self.req_id = req_id
        self.rpc_call = rpc_call
        self.data = data


def generate_req_id():
    #return str(ulid.new())
    #return b58encode(os.urandom(12))
    return uuid.uuid4().hex


def jsonapi_request(req_id, op, params):
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": op,
            "params": params
        }
    )


def jsonapi_ws_subscribed(req_id, sub_id):
    return json.dumps({
        "jsonrpc":"2.0",
        "id": req_id,
        "result": sub_id
    })


def jsonapi_ws_response(sub_id, op, result, exc=None):
    return json.dumps({
        "jsonrpc": "2.0",
        "method": op,
        "params": {
            "subscription": sub_id,
            "result": result
        }
    })

def jsonapi_response(req_id, op, result):
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": op,
            "result": result
        }
    )


def jsonapi_error(req_id, rpc_err, err_data):
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": rpc_err["code"],
                "message": rpc_err["msg"],
                "data": err_data,
            }
        }
    )


def jsonapi_parse(message):
    req_id = None
    rpc_call = None
    try:
        message = json.loads(message)
        req_id = message["id"]
        params = message.get("params", [])
        result = message.get("result", None)
        rpc_call = message["method"]
    except Exception as e:
        logging.exception(f"Error parsing RPC request: {message}")
        raise RPCCallException("PARSE_ERROR", req_id, rpc_call, str(e))

    type = None
    if rpc_call in RPC_REQUESTS:
        if rpc_call.startswith("subscribe"):
            type = RPC_TYPE_SUBSCRIBE
        elif rpc_call.startswith("unsubscribe"):
            type = RPC_TYPE_UNSUBSCRIBE
        else:
            type = RPC_TYPE_REQUEST

    if type is None:
        raise RPCCallException(RPC_ERROR["UNKNOWN_MESSAGE_TYPE"], req_id, rpc_call, params)

    return req_id, rpc_call, params, type, result


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


def rpcParent(app, params):
    try:
        block = app.retrieve_block_by_hash(bytes(params))
        if not block:
            raise RPCCallException(RPC_ERROR["UNKNOWN_HEADER_HASH"])
        return [
            list(block.header.parent),
            block.header.timeslot
        ]
    except StateKeyNoResult:
        raise RPCCallException(RPC_ERROR["UNKNOWN_HEADER_HASH"])
    except:
        raise RPCCallException(RPC_ERROR["INVALID_PARAMS"])


def rpcServiceData(app, params):
    try:
        service = app.state.services.retrieve_service_account(params[1])
        return list(service.to_serialized_bytes())
    except StateKeyNoResult:
        return None


def rpcServiceValue(app, params):
    try:
        return list(app.state.services.retrieve_storage_item(service_account_id=params[1], storage_item_hash=params[0]))
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


def rpcStatistics(app, params):
    #TODO: params should contain the header hash indicating the block whose posterior state should be used for the query
    return list(app.state.statistics.to_jam_bytes().to_bytes())


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


def rpcSubscribeBestBlock(app: PyjamazApp, params):
    # Note: initial response after subscription
    data = rpcBestBlock(app, params)
    return {"header_hash": data[0], "slot": data[1]}


def rpcSubscribeFinalizedBlock(app: PyjamazApp, params):
    data = rpcFinalizedBlock(app, params)
    return {"header_hash": data[0], "slot": data[1]}


def rpcSubscribeServiceData(app: PyjamazApp, params):
    # Note: initial response after subscription
    try:
        return {
            "header_hash": list(app.retrieve_block_hash(app.state.timeslot.number)),
            "slot": app.state.timeslot.number,
            "value": rpcServiceData(app, params)
        }
    except StateKeyNoResult:
        return None


def rpcSubscribeStatistics(app: PyjamazApp, params):
    # Note: initial response after subscription
    try:
        return {
            "header_hash": list(app.retrieve_block_hash(app.state.timeslot.number)),
            "slot": app.state.timeslot.number,
            "value": rpcStatistics(app, params)
        }
    except StateKeyNoResult:
        return None

def rpcSubscribeServiceRequest(app: PyjamazApp, params):
    # Note: initial response after subscription
    try:
        return {
            "header_hash": list(app.retrieve_block_hash(app.state.timeslot.number)),
            "slot": app.state.timeslot.number,
            "value": rpcServiceRequest(app, params)
        }
    except StateKeyNoResult:
        return None


def rpcSubscribeServiceValue(app: PyjamazApp, params):
    # Note: initial response after subscription
    try:
        return {
            "header_hash": list(app.retrieve_block_hash(app.state.timeslot.number)),
            "slot": app.state.timeslot.number,
            "value": rpcServiceValue(app, params)
        }
    except StateKeyNoResult:
        return None


def rpcSubscribeServicePreimage(app: PyjamazApp, params):
    # Note: initial response after subscription
    try:
        return {
            "header_hash": list(app.retrieve_block_hash(app.state.timeslot.number)),
            "slot": app.state.timeslot.number,
            "value": rpcServicePreimage(app, params)
        }
    except StateKeyNoResult:
        return None



# Note: The actual (realtime) (un)subscription handlers are mapped in ws_server_subscriptions.py::SubscriptionManager
RPC_REQUESTS = {
    "parameters": rpcParameters,

    "bestBlock": rpcBestBlock,
    "subscribeBestBlock": rpcSubscribeBestBlock,
    "unsubscribeBestBlock": None,

    "finalizedBlock": rpcFinalizedBlock,
    "subscribeFinalizedBlock": rpcSubscribeFinalizedBlock,
    "unsubscribeFinalizedBlock": None,

    "parent": rpcParent,
    "stateRoot": rpcStateRoot,

    "statistics": rpcStatistics,
    "subscribeStatistics": rpcSubscribeStatistics,
    "unsubscribeStatistics": None,

    "serviceData": rpcServiceData,
    "subscribeServiceData": rpcSubscribeServiceData,
    "unsubscribeServiceData": None,

    "serviceValue": rpcServiceValue,
    "subscribeServiceValue": rpcSubscribeServiceValue,
    "unsubscribeServiceValue": None,

    "servicePreimage": rpcServicePreimage,
    "subscribeServicePreimage": rpcSubscribeServicePreimage,
    "unsubscribeServicePreimage": None,

    "serviceRequest": rpcServiceRequest,
    "subscribeServiceRequest": rpcSubscribeServiceRequest,
    "unsubscribeServiceRequest": None,

    "beefyRoot": rpcBeefyRoot,
    "submitWorkPackage": rpcSubmitWorkPackage,
    "submitPreimage": rpcSubmitPreimage,
    "listServices": rpcListServices,
}
