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
            # service_id = int.from_bytes(bytes.fromhex(args.service_id.zfill(8)), byteorder='big')
            service_id = int.from_bytes(bytes.fromhex('340e8f4e'.zfill(8)), byteorder='big')
            best_block = await client.bestBlock()

            services = await client.listServices(best_block["header_hash"])

            # Get service info
            service_data = await client.serviceData(best_block["header_hash"], service_id)

            if service_data is None:
                logging.error(f'Service {service_id} not found')
                return

            # Get Parameters
            parameters = await client.parameters()


            work_package = await create_empty_workpackage(client)

            work_package.add_work_item(
                WorkItem.from_json({
                    'accumulate_gas_limit': 10000000,
                    'code_hash': '0x0806a2111844d41615be6eb7760647537b8e3f5a42f96921930913255ab4d1bd',
                    'export_count': 3072,
                    'extrinsic': [{'hash': '0x0e5751c026e543b2e8ab2eb06099daa1d1e5df47778f7787faab45cdf12fe3a8', 'len': 0}],
                    'import_segments': [],
                    'payload': '0xffffffffffffff7f00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001458b94637d0b71df0d2c83d9b7b8de847fcd15e5fffce35c8da311d53885cd8',
                    'refine_gas_limit': 1000000000,
                    'service': service_id
                })
            )

            await client.submitWorkPackageBundle(0, work_package, [], [b''])

            # best_block_sub = await client.subscribeBestBlock()
            # async for best_block in best_block_sub:
            #
            #     logging.info(f'Best block = {best_block}')
            #     wp_status = await client.workPackageStatus(
            #         best_block["header_hash"], work_package.hash(), work_package.context.anchor
            #         )
            #     logging.info(f'Status = {wp_status.to_json()}')

            wp_status_sub = await client.subscribeWorkPackageStatus(work_package.hash(), best_block["header_hash"])
            logging.info("Waiting for status updates ...")
            async for status in wp_status_sub:
                logging.info(f'Status = {status.to_json()}')

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
