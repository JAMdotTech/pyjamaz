import anyio

from typing import Dict, List, Callable
from anyio.streams.memory import MemoryObjectSendStream, MemoryObjectReceiveStream

from pyjamaz.constants import MESSAGE_TYPES


class PubSub(object):

    def __init__(self):
        #self.send_stream: MemoryObjectSendStream[Dict], self.receive_stream: MemoryObjectReceiveStream[Dict] = anyio.create_memory_object_stream[Dict](max_buffer_size=10)
        self.send_stream: MemoryObjectSendStream[Dict] = None
        self.receive_stream: MemoryObjectReceiveStream[Dict] = None
        self.send_stream, self.receive_stream = anyio.create_memory_object_stream[Dict](max_buffer_size=10)
        self.subscriptions: Dict[str, List[Callable]] = {}
        for msg_type in MESSAGE_TYPES:
            self.subscriptions[msg_type.value] = []

    def subscribe(self, topic: MESSAGE_TYPES, callback: Callable) -> None:
        if topic.value not in self.subscriptions:
            raise Exception(f"Cannot subscribe to topic {topic} (topic does not exist)")
        self.subscriptions[topic.value].append(callback)

    async def process_messages(self) -> None:
        async with self.receive_stream, anyio.create_task_group() as tg:
            async for item in self.receive_stream:
                for subscriber in self.subscriptions[item["message_type"].value]:
                    tg.start_soon(subscriber, item["data"])
