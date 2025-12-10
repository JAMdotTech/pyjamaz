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


async def get_service_registry(client) -> ServiceRegistry:
    best_block = await client.bestBlock()
    block_hash = best_block["header_hash"]
    services_registry = await client.serviceValue(block_hash, 0, b'\x10service_registry')

    return ServiceRegistry.from_jam_bytes(JamBytes(services_registry))


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

async def create_bootservice_workpackage(client: WebsocketClient, instruction: Instruction, extrinsic: List[bytes]) -> WorkPackage:
    work_package = await create_empty_workpackage(client)
    work_package.items.append(
            WorkItem(
                accumulate_gas_limit=10000000,
                code_hash=bytes.fromhex('34ce1e5be974e62476f62779abfa24a6236d0b98d8d691ee218adddf5b2176b4'),
                export_count=0,
                extrinsic=[WorkItemExtrinsic.from_blob(e) for e in extrinsic],
                import_segments=[],
                payload=instruction.to_jam_bytes().to_bytes(),
                refine_gas_limit=1000000000,
                service=0
            )
    )

    return work_package

async def main():
    setup_logging(logging.INFO)

    try:
        async with WebsocketClient(JAM_RPC_SERVER) as client:
            # Init vars
            bootstrap_service_id = 0
            registration = "test123"

            # Get Parameters
            parameters = await client.parameters()

            # Write to a binary file
            with open("test_service.pvm", "rb") as f:
                new_service_preimage = f.read()

            preimage = Preimage.extract(new_service_preimage)

            solicit_instruction = Instruction.from_json({'Solicit': {'hash': '0xcbc63dc2acb86bd8967453ef98fd4f2be2f26d7337a0937958211c128a18b442', 'len': 2}})

            create_instruction = Instruction.from_json(
                {
                    'CreateService': {
                        'code_hash': blake2b_256_hash(new_service_preimage),
                        'code_len': len(new_service_preimage),
                        'endowment': 100000,
                        'memo': '0x0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
                        'min_item_gas': 1000000,
                        'min_memo_gas': 1000000,
                        'registration': registration
                    }
                }
            )

            random_storage_instruction = Instruction.from_json(
                {'RandomStorageRefine': {
                    'seed': 3081892978,
                    'nb_items': 6
                }}
            )

            export_instruction = Instruction.from_json(
                {'Export': {
                    'data': [b'test'],
                }}
            )

            zombify_instruction = Instruction.from_json({'Zombify': {'ejector': 0}})

            eject_instruction = Instruction.from_json(
                {'Eject': {'target': 0, 'code_hash': '0x6c63e601e26279872a93b9b443aa52ad1c26e795647f63c0b7e0abff0d3680da'}}
                )

            extrinsic = [bytes(100), bytes(200), bytes(300)]

            work_package = await create_bootservice_workpackage(client, create_instruction, extrinsic)

            logging.info(f"Creating service '{preimage.program_name}'...")
            await client.submitWorkPackage(0, work_package, extrinsic)

            new_service = await client.subscribeServiceValue(bootstrap_service_id,  b'created')
            async for data in new_service:
                logging.info("Waiting for new service ID ...")
                if data:
                    new_service_id = int.from_bytes(data, byteorder='little')
                    logging.info(f'Service ID = {data[::-1].hex()} ({new_service_id})')
                    break

            # Provide preimage
            await client.submitPreimage(new_service_id, new_service_preimage)

            sub_request = await client.subscribeServiceRequest(new_service_id, blake2b_256_hash(new_service_preimage), len(new_service_preimage))
            async for data in sub_request:
                logging.info(f"Waiting for preimage ... {data}")
                if len(data) == 1:
                    break

            # service_registry = await get_service_registry(client)

            work_package = await create_empty_workpackage(client)
            work_package.items.append(
                WorkItem(
                    accumulate_gas_limit=10000000,
                    code_hash=blake2b_256_hash(new_service_preimage),
                    # code_hash=service_registry.services[0][1].code_hash,
                    export_count=0,
                    extrinsic=[],
                    import_segments=[],
                    payload=b'Testing 1, 2, 3',
                    refine_gas_limit=5000000000,
                    service=new_service_id
                    # service=service_registry.services[0][1].id
                )
            )
            logging.info('Submitting work package for new service...')
            await client.submitWorkPackage(0, work_package, extrinsic)

            last_value = await client.subscribeServiceValue(new_service_id, b'last')
            logging.info("Waiting for new last value ...")
            async for data in last_value:
                if data:
                    logging.info(f'Last value = {data}')
                    break

            logging.info('✅ Done!')
    except ConnectionRefusedError:
        logging.error(f'⚠️ Cannot connect to PyJAMaz RPC server @ {JAM_RPC_SERVER}')


if __name__ == "__main__":
    asyncio.run(main())
