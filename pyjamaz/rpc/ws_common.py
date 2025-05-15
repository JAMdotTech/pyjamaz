import json
import logging
import uuid

from pyjamaz.rpc.rpc import rpc_requests, RPC_TYPE_REQUEST, RPC_TYPE_SUBSCRIBE, RPC_TYPE_UNSUBSCRIBE

WS_UNKNOW_MESSAGE_TYPE = "UnknownMessageType"
WS_INVALID_MESSAGE_TYPE = "InvalidMessageType"
WS_INTERNAL_ERROR = "InternalError"


class RPCCallException(Exception):
    def __init__(self, reason, req_id, rpc_call, params):
        self.reason = reason
        self.req_id = req_id
        self.rpc_call = rpc_call
        self.params = params


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


def jsonapi_response(req_id, op, result, exc=None):
    """
    TODO:
    if exc:
    "error": {"code": -32602, "message": "Missing topic"},
    "error": {"code": -32601, "message": "Method not found"},
    """

    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": op,
            "result": result
        }
    )


def jsonapi_parse(message):
    try:
        message = json.loads(message)
        req_id = message["id"]
        params = message.get("params", [])
        result = message.get("result", None)
        rpc_call = message["method"]
    except Exception as e:
        logging.exception(f"Error parsing message: {message}")
        raise RPCCallException(WS_INVALID_MESSAGE_TYPE, None, None, message)

    type = None
    if rpc_call.startswith("subscribe"): 
        type = RPC_TYPE_SUBSCRIBE
    elif rpc_call.startswith("unsubscribe"):
        type = RPC_TYPE_UNSUBSCRIBE
    elif rpc_call in rpc_requests:
        type = RPC_TYPE_REQUEST

    if type is None:
        raise RPCCallException(WS_UNKNOW_MESSAGE_TYPE, req_id, rpc_call, params)

    return req_id, rpc_call, params, type, result

