import json
from typing import List, Optional, Tuple, Dict

import websockets
import asyncio

from pyjamaz.models.common import Authorizer, RefinementContext, WorkPackage, WorkItem
from pyjamaz.models.state import ServiceAccount
from pyjamaz.rpc.interface import RPCMethods
from pyjamaz.rpc.rpc import generate_req_id, jsonapi_parse, RPCCallException, jsonapi_request


class WebsocketClient(RPCMethods):

    def __init__(self, url):
        self.url = url
        self.ws = None
        self.pending = {}  # Maps request_id to asyncio.Future
        self.subs = {}

    async def __aenter__(self):
        self.ws = await websockets.connect(self.url)
        self.listener_task = asyncio.create_task(self._listener())
        return self


    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.listener_task.cancel()
        await self.ws.close()


    async def _listener(self):
        async for data in self.ws:
            if isinstance(data, bytes):
                data = data.decode("utf8")

            #print("RECEIVED DATA FROM SERVER: ", data and len(data))

            # Note: we can always trust we're dealing with one message at a time: https://stackoverflow.com/a/21025321
            try:
                # Subscriptions have a different message format, hack:
                json_data = json.loads(data)

                if "id" in json_data:
                    if json_data["id"] in self.pending:
                        self.pending[json_data["id"]].set_result(json_data["result"])
                        del self.pending[json_data["id"]]
                        #print(f"RESOLVED PENDING REQUEST ({len(self.pending)} pending)")
                        continue
                    else:
                        #print(f"REQUEST NOT PENDING????? ({len(self.pending)} pending)")
                        continue

                elif "params" in json_data and json_data["params"].get("subscription") is not None:
                    if json_data["params"]["subscription"] in self.subs:
                        #self.subs[json_data["params"]["subscription"]].set_result(json_data["result"])
                        await self.subs[json_data["params"]["subscription"]].put(json_data["params"]["result"])
                        #print(f"RESOLVED SUBSCRIPTION ({len(self.subs.keys())} pending)")
                        continue
                    else:
                        #print(f"SUBSCRIPTION NOT PENDING????? ({len(self.subs.keys())} pending)")
                        continue
                else:
                    #print("INVALID RESPONSE????????")
                    continue

            except RPCCallException as e:
                print("INVALID RESPONSE MESSAGE")
                if e.req_id and e.req_id in self.pending:
                    self.pending[e.req_id].set_result(None)
                    del self.pending[e.req_id]

            except Exception as e:
                print("UNKNOWN ERROR????????:::: ", e)


    async def _send_and_wait(self, op, params):
        req_id = generate_req_id()
        fut = asyncio.get_event_loop().create_future()
        self.pending[req_id] = fut
        req = jsonapi_request(req_id, op, params)
        await self.ws.send(req)
        response = await fut
        return response


    async def subscribe(self, op, params, result_parser):
        sub_id = await self._send_and_wait(op, params)

        qu = asyncio.Queue()
        self.subs[sub_id] = qu

        print(f"SUBSCRIBED TO {op} with id {sub_id} and params {params}")

        async def gen():
            try:
                while True:
                    res = await qu.get()
                    yield result_parser(res)
            finally:
                #TODO: unsubscribve
                # await self.ws.send(
                #     ws_frame_msg(req_id, "unsub", b"")
                # )
                self.subs.pop(sub_id, None)  # local cleanup

        return gen()


    async def parameters(self) -> Dict:
        return await self._send_and_wait("parameters", None)


    async def bestBlock(self) -> Optional[Tuple[bytes,int]]:
        res = await self._send_and_wait("bestBlock", None)
        if not res:
            return None
        res["header_hash"] = bytes(res["header_hash"])
        return res

    async def listServices(self) -> List[int]:
        return await self._send_and_wait("listServices", None)


    async def stateRoot(self, block_hash) -> bytes:
        block_hash = list(block_hash)
        res = await self._send_and_wait("stateRoot", [block_hash])
        return bytes(res)

    async def beefyRoot(self, block_hash) -> bytes:
        block_hash = list(block_hash)
        res = await self._send_and_wait("beefyRoot", [block_hash])
        return bytes(res)

    async def servicePreimage(self, block_hash: bytes, service_id: int, preimage_hash: bytes) -> Optional[bytes]:
        blob = await self._send_and_wait("servicePreimage", [block_hash, service_id, preimage_hash])
        if not blob:
            return None
        return bytes(blob)


    async def submitWorkPackage(self, core_idx:int, workpackage:WorkPackage, extrinsics:List[bytes]) -> None:
        workpackage_blob = list(workpackage.to_jam_bytes().to_bytes())
        extrinsics_blob = [list(extrinsics_item) for extrinsics_item in extrinsics]
        return await self._send_and_wait("submitWorkPackage", [core_idx, workpackage_blob, extrinsics_blob])


    async def submitPreimage(self, service_id:int , preimage_blob: bytes, block_hash: bytes) -> None:
        preimage_blob = list(preimage_blob)
        block_hash = list(block_hash)
        return await self._send_and_wait("submitPreimage", [service_id, preimage_blob, block_hash])

    async def serviceValue(self, block_hash: bytes , service_id: int, storage_key: bytes) -> Optional[bytes]:
        result = await self._send_and_wait("serviceValue", [list(block_hash), service_id, list(storage_key)])
        if result is not None:
            result = bytes(result)
        return result

    async def serviceData(self, block_hash: bytes, service_id:int) -> Optional[ServiceAccount]:
        blob = await self._send_and_wait("serviceData", [list(block_hash), service_id])
        if not blob:
            return None
        return ServiceAccount.from_serialized_bytes(bytes(blob))


    async def serviceRequest(self, block_hash: bytes, service_id:int, preimage_hash: bytes, preimage_length: int) -> Optional[ServiceAccount]:
        return await self._send_and_wait("serviceRequest", [list(block_hash), service_id, list(preimage_hash), preimage_length])


    async def subscribeServiceData(self, service_id):
        return await self.subscribe("subscribeServiceData", [service_id], lambda x: ServiceAccount.from_serialized_bytes(bytes(x)))


    async def subscribeServiceValue(self, service_id, storage_item_key):
        def result_parser(result):
            if result.get('value') is not None:
                return bytes(result.get('value'))
            return None
        return await self.subscribe("subscribeServiceValue", [service_id, list(storage_item_key), False], result_parser)


    async def subscribeServiceRequest(self, block_hash: bytes, service_id:int, preimage_hash: bytes, preimage_length: int):
        return await self.subscribe("subscribeServiceRequest", [list(block_hash), service_id, list(preimage_hash), preimage_length], lambda x: x)

