import logging
from dataclasses import dataclass

import anyio

from typing import Dict, List, Callable, Any
from anyio.streams.memory import MemoryObjectSendStream, MemoryObjectReceiveStream

from pyjamaz.constants import MESSAGE_TYPES


@dataclass
class PubSubSignal:
    topic: MESSAGE_TYPES
    data: Any


class PubSub(object):

    def __init__(self):
        #self.send_stream: MemoryObjectSendStream[Dict], self.receive_stream: MemoryObjectReceiveStream[Dict] = anyio.create_memory_object_stream[Dict](max_buffer_size=10)
        self.send_stream: MemoryObjectSendStream[PubSubSignal] = None
        self.receive_stream: MemoryObjectReceiveStream[PubSubSignal] = None
        self.send_stream, self.receive_stream = anyio.create_memory_object_stream[PubSubSignal](max_buffer_size=1000)
        self.subscriptions: Dict[str, List[Callable]] = {}
        for msg_type in MESSAGE_TYPES:
            self.subscriptions[msg_type.value] = []


    async def publish(self, message: PubSubSignal) -> None:#topic: MESSAGE_TYPES, data: any) -> None:
       await self.send_stream.send(message)


    def subscribe(self, topic: MESSAGE_TYPES, callback: Callable,) -> None:
        if topic.value not in self.subscriptions:
            raise Exception(f"Cannot subscribe to topic {topic} (topic does not exist)")
        self.subscriptions[topic.value].append(callback)


    async def process_messages(self) -> None:
        async with anyio.create_task_group() as tg:
            async for msg in self.receive_stream:
                for subscriber in self.subscriptions[msg.topic.value]:
                    tg.start_soon(subscriber, msg.data)


