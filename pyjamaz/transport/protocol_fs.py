import json
import logging
import os
import anyio

from pyjamaz.constants import MESSAGE_TYPES


logger = logging.getLogger("FSProtocol")


class FSProtocol(object):

    def __init__(self, block_dir, pubsub, app):
        self.block_dir = block_dir
        self.lock = anyio.Lock()
        self.pubsub = pubsub
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

                                self.pubsub.send_stream.send_nowait({
                                    "message_type": MESSAGE_TYPES.IMPORT_BLOCK_JSON,
                                    "data": json.load(file)
                                })

                    except Exception as e:
                        logger.error(f"Failed to process {filepath}: {e}")

                # Update the seen_files set to include the newly processed files
                seen_files.update(new_files)

            await anyio.sleep(.5)


    async def broadcast_block(self, block):
        # write block to dir
        async with self.lock:
            filepath = os.path.join(self.block_dir, f'block-{block.header.timeslot:06}.json')
            with open(filepath, 'w') as file:
                json.dump(block.to_json(), file, indent=2)
