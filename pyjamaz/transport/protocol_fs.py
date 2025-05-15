import json
import logging
import os
import anyio
from jamcodec.base import JamBytes

from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.models.block import Block
from pyjamaz.transport.pubsub import PubSubSignal
from pyjamaz.transport.types import ProtocolType


logger = logging.getLogger("pyjamaz.transport")


class FSProtocol(ProtocolType):

    def __init__(self, block_dir, app):
        self.block_dir = block_dir
        self.lock = anyio.Lock()
        self.pubsub = app.pubsub
        self.app = app

    async def listen(self):

        seen_files = set()

        while True:
            # Run the directory check in a separate thread (non-blocking)
            new_files = await anyio.to_thread.run_sync(
                lambda: {f for f in os.listdir(self.block_dir) if f.startswith('block-')} - seen_files
            )

            if new_files:
                for filename in sorted(new_files):
                    filepath = os.path.join(self.block_dir, filename)

                    try:
                        async with self.lock:

                            with open(filepath, 'r') as file:
                                if filename.startswith("block-req-"):
                                    self.pubsub.publish(PubSubSignal(topic=MESSAGE_TYPES.REQUESTED_BLOCKS, data=json.load(file)))

                                else:
                                    self.pubsub.publish(PubSubSignal(topic=MESSAGE_TYPES.RECEIVED_BLOCK,data=json.load(file)))

                    except Exception as e:
                        logging.error(f"Failed to process {filepath}: {e}")

                # Update the seen_files set to include the newly processed files
                seen_files.update(new_files)

            await anyio.sleep(.5)


    async def request_blocks(self, direction, max_blocks, block_bytes):
        block = Block.from_jam_bytes(JamBytes(block_bytes))
        blocks = []
        # TODO: take direction and max_blocks into account
        # TODO: we decode and serialize blocks unnecessary here, improve!
        while block.header.parent != bytes(32):
            block = self.app.retrieve_block_by_hash(block.header.parent)
            if not block:
                break
            blocks.append(block)

        serialized_blocks = [b.to_json() for b in blocks]

        filepath = os.path.join(self.block_dir, f'block-req-{block.header.timeslot:06}.json')
        with open(filepath, 'w') as file:
            json.dump(serialized_blocks, file, indent=2)


    async def broadcast_block(self, block):
        # write block to dir
        async with self.lock:
            filepath = os.path.join(self.block_dir, f'block-{block.header.timeslot:06}.json')
            with open(filepath, 'w') as file:
                logger.debug(f"FSProtocol dump block to disk: {filepath}")
                json.dump(block.to_json(), file, indent=2)
