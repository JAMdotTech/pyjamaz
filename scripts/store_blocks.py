import argparse
import asyncio
import logging
import os
import json
from typing import List

from jamcodec.base import JamBytes
from jamcodec.types import Vec, U32, U16, Array

from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.logger import setup_logging
from pyjamaz.models.builder import Instruction, ServiceRegistry
from pyjamaz.models.common import RefinementContext, WorkPackage, WorkItem, WorkItemExtrinsic, Preimage
from pyjamaz.rpc.ws_client import WebsocketClient
from pyjamaz.utils import base64_decode

JAM_RPC_SERVER = os.getenv('JAM_RPC_SERVER', "ws://127.0.0.1:19800")


async def main(args):
    setup_logging(logging.INFO)

    try:
        async with WebsocketClient(JAM_RPC_SERVER) as client:


            best_block = await client.bestBlock()

            # with open(os.path.join(traces_dir, f'{base_filename}.bin'), 'wb') as file:
            #     file.write(trace.to_jam_bytes().to_bytes())

            block = client.get_block(best_block.header.number)

            print(best_block.header.timeslot)


            # best_block_sub = await client.subscribeBestBlock()
            # logging.info("Waiting for best block ...")
            # async for best_block in best_block_sub:
            #
            #     pass






    except ConnectionRefusedError:
        logging.error(f'⚠️ Cannot connect to JAM RPC server @ {JAM_RPC_SERVER}')


def parse_args():
    parser = argparse.ArgumentParser(description="My asyncio CLI app")
    # parser.add_argument("service_id", help="Service ID to monitor e.g. 6e1a1155")
    # parser.add_argument(
    #     "--verbose",
    #     action="store_true",
    #     help="Enable verbose output",
    # )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
