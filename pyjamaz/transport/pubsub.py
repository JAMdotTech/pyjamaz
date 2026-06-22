import asyncio
import logging
from dataclasses import dataclass

import anyio

from typing import Dict, List, Callable, Any
from anyio.streams.memory import MemoryObjectSendStream, MemoryObjectReceiveStream

from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.settings import DEBUG


@dataclass
class PubSubSignal:
    topic: MESSAGE_TYPES
    data: Any
    ack: asyncio.Future | None = None


class PubSub(object):

    def __init__(self):
        #self.send_stream: MemoryObjectSendStream[Dict], self.receive_stream: MemoryObjectReceiveStream[Dict] = anyio.create_memory_object_stream[Dict](max_buffer_size=10)
        self.send_stream: MemoryObjectSendStream[PubSubSignal] = None
        self.receive_stream: MemoryObjectReceiveStream[PubSubSignal] = None
        # TODO fix nicer
        self.send_stream, self.receive_stream = anyio.create_memory_object_stream[PubSubSignal](max_buffer_size=100000000)
        self.subscriptions: Dict[str, List[Callable]] = {}
        for msg_type in MESSAGE_TYPES:
            self.subscriptions[msg_type.value] = []


    async def publish(self, message: PubSubSignal) -> None:#topic: MESSAGE_TYPES, data: any) -> None:
        try:
            self.send_stream.send_nowait(message)
            DEBUG and logging.debug(f"[PubSub] [{message.topic}] -> {message.data}")
        except anyio.WouldBlock:
            raise

    async def publish_and_wait(self, message: PubSubSignal) -> None:
        if message.ack is None:
            message.ack = asyncio.get_running_loop().create_future()
        await self.publish(message)
        await message.ack

    def subscribe(self, topic: MESSAGE_TYPES, callback: Callable,) -> None:
        if topic.value not in self.subscriptions:
            raise Exception(f"Cannot subscribe to topic {topic} (topic does not exist)")
        self.subscriptions[topic.value].append(callback)


    async def _safe_dispatch(self, subscriber: Callable, data: Any) -> None:
        try:
            await subscriber(data)
        except Exception:
            logging.exception("PubSub subscriber failed")

    async def _dispatch_and_ack(self, msg: PubSubSignal) -> None:
        try:
            subscribers = list(self.subscriptions[msg.topic.value])
            async with anyio.create_task_group() as tg:
                for subscriber in subscribers:
                    tg.start_soon(self._safe_dispatch, subscriber, msg.data)
        except Exception as exc:
            if msg.ack is not None and not msg.ack.done():
                msg.ack.set_exception(exc)
        else:
            if msg.ack is not None and not msg.ack.done():
                msg.ack.set_result(None)

    async def process_messages(self) -> None:
        async with anyio.create_task_group() as tg:
            async for msg in self.receive_stream:
                if msg.ack is not None:
                    tg.start_soon(self._dispatch_and_ack, msg)
                    continue
                for subscriber in self.subscriptions[msg.topic.value]:
                    tg.start_soon(self._safe_dispatch, subscriber, msg.data)

