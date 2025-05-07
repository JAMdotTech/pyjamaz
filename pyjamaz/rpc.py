import asyncio
import json
import logging
import os
import typing

import websockets
from base58 import b58encode
from websockets import WebSocketServerProtocol

import pyjamaz.graypaper_constants as gp_const
from pyjamaz.exceptions import StateKeyNoResult

if typing.TYPE_CHECKING:
    from pyjamaz.app import PyjamazApp

class Subscription:
    def __init__(self, topic: str, ws: WebSocketServerProtocol, changes_only = False):
        self.topic = topic
        self.ws = ws
        self.id = b58encode(os.urandom(16)).decode('utf-8')[:16]
        self.last_message = None
        self.changes_only = changes_only

    def __eq__(self, other):
        if isinstance(other, Subscription):
            return self.id == other.id
        return False

    def __hash__(self):
        return hash(self.id)

    def __repr__(self):
        return f"<Subscription id={self.id} topic={self.topic}>"

    async def send(self, message: typing.Any):
        if message != self.last_message or not self.changes_only:
            await self.ws.send(message)
            self.last_message = message

class SubscriptionManager:
    def __init__(self):
        self._topics: dict[str, set[Subscription]] = {}
        self._subscriptions: dict[str, Subscription] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, ws: WebSocketServerProtocol, topic: str) -> Subscription:
        async with self._lock:
            subs = self._topics.setdefault(topic, set())

            sub = Subscription(topic, ws)

            subs.add(sub)

            self._subscriptions[sub.id] = sub

            logging.info(f'{sub.id} subscribed to {topic}')

            return sub

    async def unsubscribe(self, subscription_id: str):
        async with self._lock:

            sub = self._subscriptions.pop(subscription_id, None)
            if sub is not None:
                subs = self._topics.get(sub.topic)
                if subs:
                    subs.discard(sub)
                    if not subs:
                        del self._topics[sub.topic]
                        logging.info(f'{sub.id} unsubscribed from {sub.topic}')

    async def unsubscribe_ws(self, ws: WebSocketServerProtocol, topic: str):
        async with self._lock:
            subs = self._topics.get(topic)
            if subs:
                subs.discard(ws)
                logging.info(f'{id(ws)} unsubscribed from {topic}')
                if not subs:
                    del self._topics[topic]
                    logging.info(f'Topic {topic} removed')

    async def publish(self, topic: str, data):
        async with self._lock:
            subs = list(self._topics.get(topic, ()))
        if not subs:
            return

        for sub in subs:
            if sub.ws.open:
                message = json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": sub.topic,
                        "params": {"result": data, "subscription": sub.id}
                    }
                )
                await sub.ws.send(message)
            else:
                await self.unsubscribe(sub.id)

        # await asyncio.gather(*( for ws in subs if ws.open))


async def rpc_handler(ws: WebSocketServerProtocol, app: 'PyjamazApp', manager: SubscriptionManager):
    # Keep reading requests until the client disconnects
    try:
        async for raw in ws:
            try:
                req = json.loads(raw)
                method = req.get("method")
                id_ = req.get("id")
                params = req.get("params", [])
            except json.JSONDecodeError:
                # Invalid JSON, skip
                continue

            resp = {"jsonrpc": "2.0", "id": id_}

            if method == "parameters":
                resp["result"] = {
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
                        "max_refine_code_size": gp_const.MAXIMUM_SIZE_SERVICE_CODE,
                        "basic_piece_len": gp_const.SIZE_ERASURE_CODED_PIECES,
                        "max_imports": gp_const.MAXIMUM_NUMBER_IMPORTS_WORK_PACKAGE,
                        # TODO not yet defined
                        "max_is_authorized_code_size": gp_const.MAXIMUM_SIZE_SERVICE_CODE,
                        "max_exports": gp_const.MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE,
                        "max_refine_memory": 2**16,
                        "max_is_authorized_memory": 2**16
                    }
                }

            elif method == "subscribeStatistics":
                topic = 'statistics'
                sub = await manager.subscribe(ws, topic)
                resp["result"] = sub.id

            elif method == "unsubscribeStatistics":
                await manager.unsubscribe(params[0])
                resp["result"] = None

            elif method == "bestBlock":
                resp["result"] = [
                    list(app.retrieve_block_hash(app.state.timeslot.number)),
                    app.state.timeslot.number
                ]
            elif method == "listServices":
                resp["result"] = [0]

            elif method == "serviceData":
                try:
                    service = app.state.services.retrieve_service_account(params[1])
                    resp["result"] = list(service.to_serialized_bytes())
                except StateKeyNoResult:
                    resp["result"] = None

            elif method == "servicePreimage":
                try:
                    preimage = app.state.services.retrieve_preimage(params[1], bytes(params[2]))
                    resp["result"] = list(preimage)
                except StateKeyNoResult:
                    resp["result"] = None

            # elif method == "subscribe":
            #     topic = params.get("topic")
            #     if topic:
            #         await manager.subscribe(ws, topic)
            #         resp = {"jsonrpc": "2.0", "result": f"subscribed to {topic}", "id": id_}
            #     else:
            #         resp = {
            #             "jsonrpc": "2.0",
            #             "error": {"code": -32602, "message": "Missing topic"},
            #             "id": id_
            #         }
            #
            # elif method == "unsubscribe":
            #     topic = params.get("topic")
            #     if topic:
            #         await manager.unsubscribe(ws, topic)
            #         resp = {"jsonrpc": "2.0", "result": f"unsubscribed from {topic}", "id": id_}
            #     else:
            #         resp = {
            #             "jsonrpc": "2.0",
            #             "error": {"code": -32602, "message": "Missing topic"},
            #             "id": id_
            #         }

            else:
                resp = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": "Method not found"},
                    "id": id_
                }

            await ws.send(json.dumps(resp))

    except websockets.exceptions.ConnectionClosed:
        # Clean up: remove ws from all topics
        async with manager._lock:
            for subs in manager._topics.values():
                subs.discard(ws)



async def start_rpc_server(app: 'PyjamazApp', manager: SubscriptionManager, stop_event: asyncio.Event, host="localhost", port=19800):
    async def handler(websocket):
        await rpc_handler(websocket, app, manager)

    async with websockets.serve(handler, host, port):
        logging.info(f"🛜 JSON-RPC WebSocket server listening on ws://{host}:{port}")
        await stop_event.wait()
    logging.info("WebSocket server stopped.")

