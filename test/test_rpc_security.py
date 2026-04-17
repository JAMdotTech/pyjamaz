import unittest

from pyjamaz.rpc.jsonapi import RPCCallException, RPC_ERROR, RPC_TYPE_REQUEST, jsonapi_parse


class TestRPCSecurity(unittest.TestCase):
    RPC_REQUESTS = {
        "submitPreimage": object(),
        "subscribeBestBlock": object(),
        "unsubscribeBestBlock": object(),
    }

    def test_rejects_malformed_json(self):
        with self.assertRaises(RPCCallException) as context:
            jsonapi_parse("{", self.RPC_REQUESTS)

        self.assertEqual("PARSE_ERROR", context.exception.reason)

    def test_rejects_unknown_methods(self):
        with self.assertRaises(RPCCallException) as context:
            jsonapi_parse('{"jsonrpc":"2.0","id":"1","method":"totallyUnknown","params":[]}', self.RPC_REQUESTS)

        self.assertEqual(RPC_ERROR["UNKNOWN_MESSAGE_TYPE"], context.exception.reason)

    def test_classifies_mutating_methods_as_plain_requests(self):
        req_id, rpc_call, params, rpc_type, result = jsonapi_parse(
            '{"jsonrpc":"2.0","id":"1","method":"submitPreimage","params":[1,"AA=="]}',
            self.RPC_REQUESTS,
        )

        self.assertEqual("1", req_id)
        self.assertEqual("submitPreimage", rpc_call)
        self.assertEqual([1, "AA=="], params)
        self.assertEqual(RPC_TYPE_REQUEST, rpc_type)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
