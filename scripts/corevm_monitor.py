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

            # Init vars
            # service_id = int.from_bytes(bytes.fromhex(args.service_id.zfill(8)), byteorder='big')
            service_id = int.from_bytes(bytes.fromhex('30e06bde'.zfill(8)), byteorder='big')

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
            key3 = b'\x03'
            key4 = b'\x04'
            key5 = b'\x05'

            best_block_sub = await client.subscribeBestBlock()
            logging.info("Waiting for best block ...")
            async for best_block in best_block_sub:

                logging.info(f'Best block = {best_block}')

                key3_value = await client.serviceValue(best_block["header_hash"], service_id, key3)
                logging.info(f'Key = {key3.hex()} Value = {key3_value.hex() if key3_value else "None"}')

                key4_value = await client.serviceValue(best_block["header_hash"], service_id, key4)
                logging.info(f'Key = {key4.hex()} Value = {key4_value.hex() if key4_value else "None"}')

                key5_value = await client.serviceValue(best_block["header_hash"], service_id, key5)
                logging.info(f'Key = {key5.hex()} Value = {key5_value.hex() if key5_value else "None"}')

                if key3_value is not None:
                    logging.info(f'Fetch segments..')

                    # Fetch segments
                    segment_root = key3_value[0:32]
                    logging.info(f"Segment root: {segment_root.hex()}")
                    min_segment_id = U32.decode(JamBytes(key3_value[41:45]))
                    segment_ids = list(range(min_segment_id, min_segment_id + 2273))
                    logging.info(f"Segment IDs: {segment_ids}")

                    segments = await client.fetchSegments(segment_root, segment_ids)
                    logging.info('Segment [0] = ' + segments[0].hex() + '')

                    block_number = best_block.get("slot")

                    output_dir = os.path.join(os.getcwd(), "segments")
                    os.makedirs(output_dir, exist_ok=True)
                    output_path = os.path.join(output_dir, f"{block_number}_segments.json")

                    payload = {
                        "key3_value": key3_value.hex(),
                        "segment_root": segment_root.hex(),
                        "min_segment_id": int(min_segment_id),
                        "segments": [s.hex() for s in segments],
                    }
                    with open(output_path, "w", encoding="utf-8") as handle:
                        json.dump(payload, handle, indent=2)






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
