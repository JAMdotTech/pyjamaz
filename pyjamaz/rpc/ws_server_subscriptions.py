import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any
from websockets.legacy.server import WebSocketServerProtocol

from pyjamaz.app import PyjamazApp
from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.models.block import Block
from pyjamaz.rpc.rpc import generate_req_id, jsonapi_ws_response, RPCCallException, RPC_ERROR


class WSubscription(ABC):

    def __init__(self, app: PyjamazApp, topic: str, params: Any, ws: WebSocketServerProtocol, changes_only = False):
        self.app = app
        self.topic = topic
        self.params = params
        self.ws = ws
        self.id = generate_req_id() #b58encode(os.urandom(16)).decode('utf-8')[:16]
        self.last_message = None
        self.changes_only = changes_only

    def __eq__(self, other):
        if isinstance(other, WSubscription):
            return self.id == other.id

        return False

    def __hash__(self):
        return hash(self.id)

    def __repr__(self):
        return f"<Subscription id={self.id} topic={self.topic}>"

    async def send(self, message: Any):
        if message != self.last_message or not self.changes_only:
            await self.ws.send(message)
            self.last_message = message

    @abstractmethod
    def check_params(self, data: Any):
        """ Checks registered parameters for this subscription against the data from our signal"""
        pass

    @abstractmethod
    def create_data(self, data: Any):
        """ Creates the JSONAPI result data from the data of our PubSub signal"""
        pass


class SubscriptionBestBlock(WSubscription):
    def check_params(self, data: Any):
        return True

    def create_data(self, data: Any):
        return {
            "header_hash": list(data.header.hash),
            "slot": data.header.timeslot,
        }


class SubscriptionFinalizedBlock(WSubscription):
    def check_params(self, data: Any):
        return True

    def create_data(self, data: Block):
        return {
            "header_hash": list(data.header.hash),
            "slot": data.header.timeslot,
        }


class SubscriptionStatistics(WSubscription):
    def check_params(self, data: Any):
        return True

    def create_data(self, data: Any):
        return {
            "header_hash": list(self.app.get_best_header_hash()),
            "slot": self.app.state.timeslot.number,
            "value": data
        }


class SubscriptionServiceAccount(WSubscription):
    PARAM_SERVICE_ID = 0
    DATA_SERVICE_BLOB = 1

    def check_params(self, data: Any):
        #print("CHECKING PARAMS FOR subscribeServiceData")
        if data:
            return self.params[self.PARAM_SERVICE_ID] == data[self.PARAM_SERVICE_ID]
        return True

    def create_data(self, data: Any):
        #return list(data[self.DATA_SERVICE_BLOB].to_jam_bytes().to_bytes())
        return {
            "header_hash": list(self.app.get_best_header_hash()),
            "slot": self.app.state.timeslot.number,
            "value": list(data[self.DATA_SERVICE_BLOB].to_jam_bytes().to_bytes())
        }


class SubscriptionStorageItem(WSubscription):
    PARAM_SERVICE_ID = 0
    PARAM_STORAGE_KEY = 1
    DATA_SERVICE_BLOB = 2

    def check_params(self, data: Any):
        if data:
            storage_hash = blake2b_256_hash(int(self.params[self.PARAM_SERVICE_ID]).to_bytes(length=4, byteorder="little") + bytes(self.params[self.PARAM_STORAGE_KEY]))
            print("CHECKING PARAMS FOR subscribeServiceValue", self.params[self.PARAM_SERVICE_ID] == data[self.PARAM_SERVICE_ID] and list(storage_hash) == list(data[self.PARAM_STORAGE_KEY]))
            return self.params[self.PARAM_SERVICE_ID] == data[self.PARAM_SERVICE_ID] and list(storage_hash) == list(data[self.PARAM_STORAGE_KEY])
        return True

    def create_data(self, data: Any):
        #return list(data[self.DATA_SERVICE_BLOB])
        return {
            "header_hash": list(self.app.get_best_header_hash()),
            "slot": self.app.state.timeslot.number,
            "value": list(data[self.DATA_SERVICE_BLOB])
        }


class SubscriptionPreimage(WSubscription):
    PARAM_SERVICE_ID = 0
    PARAM_PREIMAGE_HASH = 1
    DATA_PREIMAGE_BLOB = 3

    def check_params(self, data: Any):
        #print("CHECKING PARAMS FOR subscribeServicePreimage")
        if data:
            return self.params[self.PARAM_SERVICE_ID] == data[self.PARAM_SERVICE_ID] and self.params[self.PARAM_PREIMAGE_HASH] == data[self.PARAM_PREIMAGE_HASH]
        return True

    def create_data(self, data: Any):
        #return list(data[self.DATA_PREIMAGE_BLOB])
        return {
            "header_hash": list(self.app.get_best_header_hash()),
            "slot": self.app.state.timeslot.number,
            "value": list(data[self.DATA_PREIMAGE_BLOB])
        }


class SubscriptionPreimageAvailability(WSubscription):
    PARAM_SERVICE_ID = 0
    PARAM_PREIMAGE_HASH = 1
    PARAM_PREIMAGE_LENGTH = 2
    DATA_SERVICE_ID = 0
    DATA_PREIMAGE_HASH = 1
    DATA_PREIMAGE_LENGTH = 2
    DATA_PREIMAGE_BLOB = 3

    def check_params(self, data: Any):
        #print("CHECKING PARAMS FOR subscribeServicePreimageAvailability",data,tt)
        if data:
            return (self.params[self.PARAM_SERVICE_ID] == data[self.DATA_SERVICE_ID] and
                    bytes(self.params[self.PARAM_PREIMAGE_HASH]) == data[self.DATA_PREIMAGE_HASH] and
                    self.params[self.PARAM_PREIMAGE_LENGTH] == data[self.DATA_PREIMAGE_LENGTH])
        return True

    def create_data(self, data: Any):
        #return list(data[self.DATA_PREIMAGE_BLOB])
        return {
            "header_hash": list(self.app.get_best_header_hash()),
            "slot": self.app.state.timeslot.number,
            "value": list(data[self.DATA_PREIMAGE_BLOB])
        }


class SubscriptionSyncStatus(WSubscription):

    def check_params(self, data: Any):
        return True

    def create_data(self, data: Any):
        return "Completed" #"InProgress"


class SubscriptionManager:

    SUBSCRIPTION_MAP = {
        "subscribeBestBlock": SubscriptionBestBlock,
        "subscribeFinalizedBlock": SubscriptionFinalizedBlock,
        "subscribeStatistics": SubscriptionStatistics,
        "subscribeServiceData": SubscriptionServiceAccount,
        "subscribeServiceValue": SubscriptionStorageItem,
        "subscribePreimage": SubscriptionPreimage,
        "subscribeServiceRequest": SubscriptionPreimageAvailability,
        "subscribeSyncStatus": SubscriptionSyncStatus,  #TODO: hook to networking events
    }

    def __init__(self, server: "WebSocketServer"):
        self._topics: dict[str, set[WSubscription]] = {}
        self._subscriptions: dict[str, WSubscription] = {}
        self._lock = asyncio.Lock()
        self.server = server

        # Subscribe to all broadcast messages relevant for our RPC
        self.server.app.pubsub.subscribe(MESSAGE_TYPES.BEST_BLOCK, self.broadcast_best_block)
        self.server.app.pubsub.subscribe(MESSAGE_TYPES.FINALIZED_BLOCK, self.broadcast_finalized_block)
        self.server.app.pubsub.subscribe(MESSAGE_TYPES.STATISTICS, self.broadcast_stats)
        self.server.app.pubsub.subscribe(MESSAGE_TYPES.SERVICE_ACCOUNT, self.broadcast_service_data)
        self.server.app.pubsub.subscribe(MESSAGE_TYPES.STORAGE_ITEM, self.broadcast_service_value)
        self.server.app.pubsub.subscribe(MESSAGE_TYPES.PREIMAGE, self.broadcast_preimage)
        self.server.app.pubsub.subscribe(MESSAGE_TYPES.PREIMAGE_AVAILABILITY, self.broadcast_preimage_availability)

    async def subscribe(self, ws: WebSocketServerProtocol, req_id, topic: str, params: Any) -> WSubscription:
        async with self._lock:
            subs = self._topics.setdefault(topic, set())
            sub_cls = self.SUBSCRIPTION_MAP.get(topic, None)
            if not sub_cls:
                raise RPCCallException(RPC_ERROR["UNKNOWN_MESSAGE_TYPE"], req_id, topic, params)
            sub = sub_cls(self.server.app, topic, params, ws)
            subs.add(sub)
            self._subscriptions[sub.id] = sub
            logging.info(f'{sub.id} subscribed to {topic}')
            return sub

    async def unsubscribe(self, subscription_id: str):
        async with self._lock:
            removed_sub_id = None
            sub = self._subscriptions.pop(subscription_id, None)
            if sub is not None:
                subs = self._topics.get(sub.topic)
                if subs:
                    removed_sub_id = sub.id
                    subs.discard(sub)
                    if not subs:
                        del self._topics[sub.topic]
                        logging.info(f'{sub.id} unsubscribed from {sub.topic}')

            return removed_sub_id

    async def broadcast_best_block(self, message):
        await self.broadcast("subscribeBestBlock", message)

    async def broadcast_finalized_block(self, message):
        await self.broadcast("subscribeFinalizedBlock", message)

    async def broadcast_stats(self, message):
        await self.broadcast("subscribeStatistics", message)

    async def broadcast_service_data(self, message):
        await self.broadcast("subscribeServiceData", message)

    async def broadcast_service_value(self, message):
        await self.broadcast("subscribeServiceValue", message)

    async def broadcast_preimage(self, message):
        await self.broadcast("subscribePreimage", message)

    async def broadcast_preimage_availability(self, message):
        await self.broadcast("subscribeServiceRequest", message)

    async def broadcast(self, topic: str, data):
        async with self._lock:
            subs = list(self._topics.get(topic, ()))

        if not subs:
            return

        for sub in subs:
            if not sub.check_params(data):
                continue

            msg_data = sub.create_data(data)
            message = jsonapi_ws_response(sub.id, sub.topic, msg_data)
            try:
                print("SENDING SUBDATA:", sub.id, sub.topic, msg_data)
                await sub.ws.send(message)
            except Exception as e:
                print(f"ERROR {e}")
                await self.unsubscribe(sub.id)
