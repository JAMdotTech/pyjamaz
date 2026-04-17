import json
import logging
import uuid

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
        "jsonrpc": "2.0",
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


def jsonapi_parse(message, rpc_requests):
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

    rpc_type = None
    if rpc_call in rpc_requests:
        if rpc_call.startswith("subscribe"):
            rpc_type = RPC_TYPE_SUBSCRIBE
        elif rpc_call.startswith("unsubscribe"):
            rpc_type = RPC_TYPE_UNSUBSCRIBE
        else:
            rpc_type = RPC_TYPE_REQUEST

    if rpc_type is None:
        raise RPCCallException(RPC_ERROR["UNKNOWN_MESSAGE_TYPE"], req_id, rpc_call, params)

    return req_id, rpc_call, params, rpc_type, result
