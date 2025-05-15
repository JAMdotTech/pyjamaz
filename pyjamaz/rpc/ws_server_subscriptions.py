import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any
from websockets.legacy.server import WebSocketServerProtocol

from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.rpc.ws_common import jsonapi_response, generate_req_id


class WSubscription(ABC):

    def __init__(self, topic: str, params: Any, ws: WebSocketServerProtocol, changes_only = False):
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


class SubscriptionStatistics(WSubscription):

    def check_params(self, data: Any):
        return True

    def create_data(self, data: Any):
        return data


class SubscriptionServiceAccount(WSubscription):
    PARAM_SERVICE_ID = 0
    DATA_SERVICE_BLOB = 1

    def check_params(self, data: Any):
        #print("CHECKING PARAMS FOR subscribeServiceData")
        if data:
            return self.params[self.PARAM_SERVICE_ID] == data[self.PARAM_SERVICE_ID]
        return True

    def create_data(self, data: Any):
        return list(data[self.DATA_SERVICE_BLOB].to_jam_bytes().to_bytes())


class SubscriptionStorageItem(WSubscription):
    PARAM_SERVICE_ID = 0
    PARAM_STORAGE_KEY = 1
    DATA_SERVICE_BLOB = 2

    def check_params(self, data: Any):
        #print("CHECKING PARAMS FOR subscribeServiceValue", data, self.params[self.PARAM_SERVICE_ID] == data[self.PARAM_SERVICE_ID] and self.params[self.PARAM_STORAGE_KEY] == data[self.PARAM_STORAGE_KEY])
        if data:
            return self.params[self.PARAM_SERVICE_ID] == data[self.PARAM_SERVICE_ID] and self.params[self.PARAM_STORAGE_KEY] == data[self.PARAM_STORAGE_KEY]
        return True

    def create_data(self, data: Any):
        return list(data[self.DATA_SERVICE_BLOB])


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
        return list(data[self.DATA_PREIMAGE_BLOB])


class SubscriptionManager:

    SUBSCRIPTION_MAP = {
        "subscribeStatistics": SubscriptionStatistics,
        "subscribeServiceData": SubscriptionServiceAccount,
        "subscribeServiceValue": SubscriptionStorageItem,
        "subscribePreimage": SubscriptionPreimage,
    }

    def __init__(self, server: "WebSocketServer"):
        self._topics: dict[str, set[WSubscription]] = {}
        self._subscriptions: dict[str, WSubscription] = {}
        self._lock = asyncio.Lock()
        self.server = server

        # Subscribe to all broadcast messages relevant for our RPC
        self.server.app.pubsub.subscribe(MESSAGE_TYPES.STATISTICS, self.broadcast_stats)
        self.server.app.pubsub.subscribe(MESSAGE_TYPES.SERVICE_ACCOUNT, self.broadcast_service_data)
        self.server.app.pubsub.subscribe(MESSAGE_TYPES.STORAGE_ITEM, self.broadcast_service_value)
        self.server.app.pubsub.subscribe(MESSAGE_TYPES.PREIMAGE, self.broadcast_preimage)

    async def subscribe(self, ws: WebSocketServerProtocol, topic: str, params: Any) -> WSubscription:
        async with self._lock:
            subs = self._topics.setdefault(topic, set())
            sub_cls = self.SUBSCRIPTION_MAP.get(topic, None)
            if not sub_cls:
                raise Exception(f"Subscription topic not mapped: {topic}")
            sub = sub_cls(topic, params, ws)
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


    async def broadcast_stats(self, message):
        await self.broadcast("subscribeStatistics", message)

    async def broadcast_service_data(self, message):
        await self.broadcast("subscribeServiceData", message)

    async def broadcast_service_value(self, message):
        await self.broadcast("subscribeServiceValue", message)

    async def broadcast_preimage(self, message):
        await self.broadcast("subscribePreimage", message)

    async def broadcast(self, topic: str, data):
        async with self._lock:
            subs = list(self._topics.get(topic, ()))

        #print("BROADCAST: ",topic, len(subs))

        if not subs:
            return

        for sub in subs:
            if sub.check_params(data):
                continue

            msg_data = sub.create_data(data)
            #print(f"SENDING {topic} : {len(msg_data)}")
            message = jsonapi_response(sub.id, sub.topic, msg_data)
            try:
                await sub.ws.send(message)
            except:
                await self.unsubscribe(sub.id)
