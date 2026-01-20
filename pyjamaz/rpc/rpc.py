import json
import logging
import uuid

from jamcodec.base import JamBytes

import pyjamaz.graypaper_constants as gp_const
from pyjamaz.app import PyjamazApp
from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.models.block import Preimage
from pyjamaz.models.builder import ServiceRegistry
from pyjamaz.models.common import WorkPackage, WorkPackageBundle, WorkPackageStatus
from pyjamaz.settings import DEBUG
from pyjamaz.utils import format_hash, base64_encode, base64_decode, summarize_blobs

#TODO: enum
RPC_TYPE_REQUEST = 1
RPC_TYPE_SUBSCRIBE = 2
RPC_TYPE_UNSUBSCRIBE = 3


RPC_ERROR = {
    "UNKNOWN_HEADER_HASH": {"code": 3000, "msg": "The given header hash is not known"},
    "UNKNOWN_MESSAGE_TYPE": {"code": -32601, "msg": "Method not found"},
    "INVALID_PARAMS": {"code": -32602, "msg": "Invalid params"},
    "PARSE_ERROR": {"code": -32700, "msg": "Parse error"},
    "UNKNOWN_SEGMENT": {
        "code": 4000,
        "msg": "Data recovery error: Data can not be recovered"
    },
}


class RPCCallException(Exception):
    def __init__(self, reason, req_id=None, rpc_call=None, data=None):
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
            "max_service_code_size": gp_const.MAXIMUM_SIZE_SERVICE_CODE,
            "basic_piece_len": gp_const.SIZE_ERASURE_CODED_PIECES,
            "max_imports": gp_const.MAXIMUM_NUMBER_IMPORTS_WORK_PACKAGE,
            "max_authorizer_code_size": gp_const.MAXIMUM_SIZE_IS_AUTH_CODE,
            # TODO not yet defined in JIP2
            "max_exports": gp_const.MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE,
            # "max_refine_memory": 2**16,
            # "max_is_authorized_memory": 2**16,
            "slot_period_sec": gp_const.SLOT_PERIOD,
            "epoch_tail_start": gp_const.TICKET_SUBMISSION_END_SLOT,
            "core_count": gp_const.CORE_COUNT,
            "segment_piece_count": gp_const.MAXIMUM_SIZE_ENCODED_WORK_PACKAGE,
            "max_report_elective_data": 49152, # TODO
            "transfer_memo_size": gp_const.TRANSFER_MEMO_SIZE,
        }
    }


def rpcBestBlock(app, params):
    return {"header_hash": base64_encode(app.retrieve_block_hash(app.working_state.timeslot.number)), "slot": app.working_state.timeslot.number}


def rpcFinalizedBlock(app, params):
    return [base64_encode(app.retrieve_block_hash(app.working_state.timeslot.number)), app.working_state.timeslot.number]


def rpcParent(app, params):
    try:
        block = app.retrieve_block_by_hash(base64_decode(params[0]))
        if not block:
            raise RPCCallException(RPC_ERROR["UNKNOWN_HEADER_HASH"])
        return [
            base64_encode(block.header.parent),
            block.header.timeslot
        ]
    except StateKeyNoResult:
        raise RPCCallException(RPC_ERROR["UNKNOWN_HEADER_HASH"])
    except:
        raise RPCCallException(RPC_ERROR["INVALID_PARAMS"])


def rpcServiceData(app, params):
    try:
        service = app.working_state.services.retrieve_service_account(params[1])
        return base64_encode(service.to_serialized_bytes())
    except StateKeyNoResult:
        return None


def rpcListServices(app: PyjamazApp, params):
    services = [0]
    try:
        # Check bootstrap service for service registry
        services_registry = app.working_state.services.retrieve_storage_item(0, b'\x10service_registry')
        services_registry = ServiceRegistry.from_jam_bytes(JamBytes(services_registry))
        services += [info.id for meta, info in services_registry.services]
    except StateKeyNoResult:
        pass
    return services


def rpcServicePreimage(app, params):
    try:
        return base64_encode(app.working_state.services.retrieve_preimage(params[1], base64_decode(params[2])))
    except StateKeyNoResult:
        return None


def rpcStateRoot(app: PyjamazApp, params):

    header_hash = base64_decode(params[0])
    for n, block in enumerate(reversed(app.working_state.recent_history.recent_blocks)):
        if block.header_hash == header_hash:
            if n == 0:
                return base64_encode(app.working_state.state_root)
            else:
                return base64_encode(block.state_root)

    return None


def rpcStatistics(app, params):
    #TODO: params should contain the header hash indicating the block whose posterior state should be used for the query
    return base64_encode(app.working_state.statistics.to_jam_bytes().to_bytes())


def rpcBeefyRoot(app: PyjamazApp, params):
    header_hash = base64_decode(params[0])
    return base64_encode(app.get_beefy_root(header_hash))


def rpcSubmitWorkPackage(app: PyjamazApp, params):
    #TODO: should assign to a specific core
    ex = [base64_decode(x) for x in params[2]]
    wp = WorkPackage.from_jam_bytes(JamBytes(base64_decode(params[1])))
    DEBUG and logging.debug(f'Received workpackage {format_hash(wp.hash())}')
    logging.warning(
        "submitWorkPackage extrinsics %s count=%s summary=%s",
        format_hash(wp.hash()),
        len(ex),
        summarize_blobs(ex),
    )
    app.add_work_package(wp, ex)


def rpcSubmitWorkPackageBundle(app: PyjamazApp, params):
    #TODO: should assign to a specific core
    raw_data = base64_decode(params[1])

    def scrub_param(param, max_str_len=512, max_list_len=20):
        if isinstance(param, str):
            if len(param) <= max_str_len:
                return param
            return f"{param[:256]}...{param[-256:]}"
        if isinstance(param, list):
            items = [scrub_param(p, max_str_len, max_list_len) for p in param[:max_list_len]]
            if len(param) > max_list_len:
                items.append("...truncated")
            return items
        if isinstance(param, dict):
            return {k: scrub_param(v, max_str_len, max_list_len) for k, v in param.items()}
        return param

    def summarize_param(param):
        if isinstance(param, str):
            return f"str(len={len(param)})"
        if isinstance(param, (bytes, bytearray)):
            return f"bytes(len={len(param)})"
        if isinstance(param, list):
            return f"list(len={len(param)})"
        if isinstance(param, dict):
            return f"dict(keys={list(param.keys())})"
        return type(param).__name__

    def summarize_extrinsics_param(param):
        if param is None:
            return "none"
        if isinstance(param, dict):
            keys = list(param.keys())
            items = param.get("extrinsics", param.get("extrinsic_data"))
            if isinstance(items, list):
                item_len = len(items)
                first_len = len(items[0]) if items and isinstance(items[0], str) else None
                return f"dict(keys={keys}, items={item_len}, first_len={first_len})"
            return f"dict(keys={keys}, items_type={type(items).__name__})"
        if isinstance(param, list):
            first_len = len(param[0]) if param and isinstance(param[0], str) else None
            return f"list(len={len(param)}, first_len={first_len})"
        return summarize_param(param)

    def decode_extrinsics_param(param):
        if param is None:
            return []
        items = None
        if isinstance(param, dict):
            if "extrinsics" in param:
                items = param["extrinsics"]
            elif "extrinsic_data" in param:
                items = param["extrinsic_data"]
        else:
            items = param

        if not items:
            return []
        if not isinstance(items, list):
            logging.warning("Unexpected extrinsics param type", extra={"type": type(items).__name__})
            return []

        extrinsics = []
        for idx, item in enumerate(items):
            try:
                extrinsics.append(base64_decode(item))
            except Exception as exc:
                logging.warning("Failed to decode extrinsic from bundle params", extra={"index": idx}, exc_info=exc)
        return extrinsics

    try:
        logging.warning(
            "submitWorkPackageBundle params: %s",
            json.dumps(scrub_param(params), sort_keys=True),
        )
        wpb = WorkPackageBundle.from_jam_bytes(JamBytes(raw_data))
        DEBUG and logging.debug(
            f'Received workpackage bundle {format_hash(wpb.work_package.hash())} extrinsics={len(wpb.extrinsic_data)}'
        )
        logging.warning(
            "submitWorkPackageBundle decoded extrinsics %s count=%s summary=%s",
            format_hash(wpb.work_package.hash()),
            len(wpb.extrinsic_data),
            summarize_blobs(wpb.extrinsic_data),
        )
        app.add_work_package_bundle(wpb)
    except Exception as exc:
        extrinsics_param = None
        if len(params) >= 4:
            extrinsics_param = params[3]
        elif len(params) >= 3:
            extrinsics_param = params[2]
        summary = {
            "params_len": len(params),
            "params_types": [summarize_param(p) for p in params],
            "core_idx": params[0] if params else None,
            "workpackage_b64_len": len(params[1]) if len(params) > 1 and isinstance(params[1], str) else None,
            "raw_len": len(raw_data),
            "raw_head": raw_data[:16].hex(),
            "extrinsics_param": summarize_extrinsics_param(extrinsics_param),
        }
        logging.warning("submitWorkPackageBundle payload summary: %s", json.dumps(summary, sort_keys=True))
        logging.warning("Failed to decode work package bundle; falling back to work package", exc_info=exc)
        wp = WorkPackage.from_jam_bytes(JamBytes(raw_data))
        extrinsics = decode_extrinsics_param(extrinsics_param)
        logging.warning(
            "submitWorkPackageBundle fallback extrinsics %s count=%s summary=%s",
            format_hash(wp.hash()),
            len(extrinsics),
            summarize_blobs(extrinsics),
        )
        DEBUG and logging.debug(
            f'Received workpackage bundle as workpackage {format_hash(wp.hash())} extrinsics={len(extrinsics)}'
        )
        app.add_work_package(wp, extrinsics)


def rpcSubmitWorkPackageExtrinsics(app: PyjamazApp, params):
    if len(params) < 2:
        raise RPCCallException(RPC_ERROR["INVALID_PARAMS"])

    def decode_hash_param(param):
        if isinstance(param, bytes):
            return param
        if isinstance(param, str):
            try:
                return base64_decode(param)
            except Exception:
                hex_str = param[2:] if param.startswith("0x") else param
                return bytes.fromhex(hex_str)
        raise RPCCallException(RPC_ERROR["INVALID_PARAMS"])

    def decode_extrinsics_param(param):
        if param is None:
            return []
        items = None
        if isinstance(param, dict):
            if "extrinsics" in param:
                items = param["extrinsics"]
            elif "extrinsic_data" in param:
                items = param["extrinsic_data"]
        else:
            items = param

        if not items:
            return []
        if not isinstance(items, list):
            raise RPCCallException(RPC_ERROR["INVALID_PARAMS"])

        extrinsics = []
        for item in items:
            extrinsics.append(base64_decode(item))
        return extrinsics

    work_package_hash = decode_hash_param(params[0])
    extrinsics = decode_extrinsics_param(params[1])
    logging.warning(
        "submitWorkPackageExtrinsics %s count=%s summary=%s",
        format_hash(work_package_hash),
        len(extrinsics),
        summarize_blobs(extrinsics),
    )
    app.work_package_extrinsics.add_by_hash(work_package_hash, extrinsics)
    return True


def rpcSubmitPreimage(app: PyjamazApp, params):
    preimage_blob = base64_decode(params[1])
    pr = Preimage(requester=params[0], blob=preimage_blob)
    app.block_extrinsic.add_preimage(pr)


def rpcServiceRequest(app: PyjamazApp, params):
    try:
        return app.working_state.services.retrieve_preimage_availability(params[1], base64_decode(params[2]), params[3])
    except StateKeyNoResult:
        return None


def rpcFetchSegments(app: PyjamazApp, params):
    """
    """
    segment_root = base64_decode(params[0])
    logging.info(f'Fetching segments for root: {format_hash(segment_root)}')
    segments = app.segment_store.get(segment_root)
    if segments is None:
        raise RPCCallException("UNKNOWN_SEGMENT")

    requested_segments = []
    DEBUG and logging.debug(f'Requested segments: {format_hash(segment_root)} {params[1]}')
    logging.info(f'Requested segments: {format_hash(segment_root)} {params[1]}')

    for requested_index in params[1]:
        requested_segments.append(base64_encode(segments[requested_index]))

    DEBUG and logging.debug(f'Requested segments: {requested_segments}')
    logging.info(f'Requested segments: {requested_segments}')
    return requested_segments


def rpcSyncState(app: PyjamazApp, params):
    return {"num_peers": 0, "status": "Completed"} #"InProgress"


def rpcSubscribeBestBlock(app: PyjamazApp, params):
    # Note: initial response after subscription
    return rpcBestBlock(app, params)


def rpcSubscribeFinalizedBlock(app: PyjamazApp, params):
    return rpcFinalizedBlock(app, params)


def rpcSubscribeServiceData(app: PyjamazApp, params):
    # Note: initial response after subscription
    try:
        return {
            "header_hash": base64_encode(app.retrieve_block_hash(app.working_state.timeslot.number)),
            "slot": app.working_state.timeslot.number,
            "value": rpcServiceData(app, params)
        }
    except StateKeyNoResult:
        return None


def rpcSubscribeStatistics(app: PyjamazApp, params):
    # Note: initial response after subscription
    try:
        return {
            "header_hash": base64_encode(app.retrieve_block_hash(app.working_state.timeslot.number)),
            "slot": app.working_state.timeslot.number,
            "value": rpcStatistics(app, params)
        }
    except StateKeyNoResult:
        return None


def rpcSubscribeServiceRequest(app: PyjamazApp, params):
    # Note: initial response after subscription
    try:
        return {
            "header_hash": base64_encode(app.retrieve_block_hash(app.working_state.timeslot.number)),
            "slot": app.working_state.timeslot.number,
            "value": rpcServiceRequest(app, [None, params[0], params[1], params[2]])
        }
    except StateKeyNoResult:
        return None

def rpcServiceValue(app: PyjamazApp, params):
    try:
        return base64_encode(app.working_state.services.retrieve_storage_item(
            service_account_id=params[1], storage_item_hash=base64_decode(params[2]))
        )
    except StateKeyNoResult:
        return None

def rpcSubscribeServiceValue(app: PyjamazApp, params):
    # Note: initial response after subscription
    try:
        return {
            "header_hash": base64_encode(app.retrieve_block_hash(app.working_state.timeslot.number)),
            "slot": app.working_state.timeslot.number,
            "value": rpcServiceValue(app, [None] + params)
        }
    except StateKeyNoResult:
        return None


def rpcSubscribeServicePreimage(app: PyjamazApp, params):
    # Note: initial response after subscription
    try:
        return {
            "header_hash": base64_encode(app.retrieve_block_hash(app.working_state.timeslot.number)),
            "slot": app.working_state.timeslot.number,
            "value": rpcServicePreimage(app, params)
        }
    except StateKeyNoResult:
        return None


def rpcSubscribeSyncStatus(app: PyjamazApp, params):
    # Note: initial response after subscription
    try:
        return "Completed" #"InProgress"
    except StateKeyNoResult:
        return None


def rpcSubscribeWorkPackageStatus(app: PyjamazApp, params):
    # Note: initial response after subscription

    work_package_hash = base64_decode(params[0])
    anchor = base64_decode(params[1])
    if work_package_hash in app.work_package_queue:
        value = app.work_package_queue[work_package_hash].status.to_json()
    else:
        value = WorkPackageStatus(Failed='Not found').to_json()

    return {
        "header_hash": base64_encode(app.retrieve_block_hash(app.working_state.timeslot.number)),
        "slot": app.working_state.timeslot.number,
        "value": value #rpcServiceRequest(app, [None, params[0], params[1], params[2]])
    }


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
    "submitWorkPackageBundle": rpcSubmitWorkPackageBundle,
    "submitWorkPackageExtrinsics": rpcSubmitWorkPackageExtrinsics,
    "submitPreimage": rpcSubmitPreimage,
    "listServices": rpcListServices,
    "fetchSegments": rpcFetchSegments,

    "syncState": rpcSyncState,
    "subscribeSyncStatus": rpcSubscribeSyncStatus,
    "unsubscribeSyncStatus": None,

    "subscribeWorkPackageStatus": rpcSubscribeWorkPackageStatus,
    "unsubscribeWorkPackageStatus": None,
}
