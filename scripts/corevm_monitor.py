import argparse
import asyncio
import logging
import os
from typing import List

from jamcodec.base import JamBytes

from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.logger import setup_logging
from pyjamaz.models.builder import Instruction, ServiceRegistry
from pyjamaz.models.common import RefinementContext, WorkPackage, WorkItem, WorkItemExtrinsic, Preimage
from pyjamaz.rpc.ws_client import WebsocketClient
from pyjamaz.utils import base64_decode

JAM_RPC_SERVER = os.getenv('JAM_RPC_SERVER', "ws://127.0.0.1:19800")


async def create_empty_workpackage(client: WebsocketClient) -> WorkPackage:
    best_block = await client.bestBlock()
    block_hash = best_block["header_hash"]
    block_timeslot = best_block["slot"]

    state_root = await client.stateRoot(block_hash)
    beefy_root = await client.beefyRoot(block_hash)

    context = RefinementContext(
        anchor=block_hash,
        state_root=state_root,
        beefy_root=beefy_root,
        lookup_anchor=block_hash,
        lookup_anchor_slot=block_timeslot,
        prerequisites=[]
    )

    work_package = WorkPackage(
        authorization=b'',
        auth_code_host=0,
        auth_code_hash=bytes.fromhex('f8d86b97d65319a078e5840f1614c296a5254217794dcc910e72ca174e3c2e86'),
        authorizer_config=b'',
        context=context,
        items=[]
    )

    return work_package


async def main(args):
    setup_logging(logging.INFO)

    try:
        async with WebsocketClient(JAM_RPC_SERVER) as client:
            # Init vars
            service_id = int.from_bytes(bytes.fromhex(args.service_id.zfill(8)), byteorder='big')

            best_block = await client.bestBlock()

            services = await client.listServices(best_block["header_hash"])

            # Get service info
            service_data = await client.serviceData(best_block["header_hash"], service_id)

            if service_data is None:
                logging.error(f'Service {service_id} not found')
                return

            # Get Parameters
            parameters = await client.parameters()


            # Check storage items
            key1 = b'\x03'
            key2 = b'\x04'
            key3 = b'\x05'

            best_block_sub = await client.subscribeBestBlock()
            logging.info("Waiting for best block ...")
            async for best_block in best_block_sub:

                logging.info(f'Best block = {best_block}')

                value = await client.serviceValue(best_block["header_hash"], service_id, key2)
                logging.info(f'Key = {key2.hex()} Value = {value}')

                value = await client.serviceValue(best_block["header_hash"], service_id, key3)
                logging.info(f'Key = {key3.hex()} Value = {value}')

                value = await client.serviceValue(best_block["header_hash"], service_id, key1)
                logging.info(f'Key = {key1.hex()} Value = {value}')

                if value is not None:
                    logging.info(f'Fetch segments..')

                    # Fetch segment
                    segments = await client.fetchSegments(value[0:32], [0])
                    logging.info(segments)



    except ConnectionRefusedError:
        logging.error(f'⚠️ Cannot connect to JAM RPC server @ {JAM_RPC_SERVER}')


def parse_args():
    parser = argparse.ArgumentParser(description="My asyncio CLI app")
    parser.add_argument("service_id", help="Service ID to monitor e.g. 6e1a1155")
    # parser.add_argument(
    #     "--verbose",
    #     action="store_true",
    #     help="Enable verbose output",
    # )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
