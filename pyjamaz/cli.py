import asyncio
import logging
from asyncio import CancelledError
from datetime import datetime
import json
import os
import shutil
import socket
from typing import Dict, List, Callable

import anyio

import time
from os import path

import asyncclick as click
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from asyncclick import BadParameter
from deepdiff import DeepDiff

from jamcodec.base import JamBytes
from pyjamaz.app import PyjamazApp, AppConfig, Keys
from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.graypaper_constants import COMMON_ERA, EPOCH_TIMESLOTS
from pyjamaz.logger import setup_logging
from pyjamaz.models.common import ValidatorData
from pyjamaz.models.stf_output import STFOutput
from pyjamaz.storage import LevelDBStorage, InMemoryStorage
from pyjamaz.models.block import Block, Header
from pyjamaz.models.state import JamState
from pyjamaz.transport.generate_cert import generate_cert, write_cert
from pyjamaz.transport.protocol_fs import FSProtocol
from pyjamaz.transport.protocol_jamnp_s import JAMNPS

data_dir = path.join(path.dirname(path.abspath(__file__)), 'data')
default_db_path = path.join(data_dir, 'db')


logger = logging.getLogger(__name__)


def initialize_app(read_state=True, memory_storage=False, keys=None, common_era=None, custom_db_path=None) -> PyjamazApp:

    # Load SRS
    with open(path.join(data_dir, 'zcash-srs-2-11-uncompressed.bin'), 'rb') as fp:
        ring_data = fp.read()

    # Initiate storage engine
    try:
        if memory_storage:
            storage_engine = InMemoryStorage()
        else:
            storage_engine = LevelDBStorage.create_from_file(custom_db_path or default_db_path)

    except IOError as e:
        logger.error(f'Could not initialize storage engine: {str(e)}')
        exit(2)

    # Set common era
    if not common_era:
        common_era = COMMON_ERA

    # Initialize app
    config = AppConfig(
        ring_data=ring_data,
        storage_engine=storage_engine,
        keys=keys,
        common_era=common_era
    )

    app = PyjamazApp(config=config)

    if read_state:
        app.state = app.retrieve_jam_state()
        app.latest_epoch = app.state.timeslot.epoch_number()

    return app


# CLI commands


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


def create_debug_block_bytes(app: PyjamazApp, traces_dir: str):
    async def debug_import_block(data):
        logger.debug(f"📦 Importing block from bytes")
        block = Block.from_jam_bytes(JamBytes(data))

        if block.header.timeslot > app.state.timeslot.number or (app.state.timeslot.number == 0 and not app.should_produce_block()):

            if traces_dir:
                pre_state = app.state.to_json()

            output = await app.import_block(block)

            if traces_dir:
                await store_trace(pre_state, block, output, app, traces_dir)

            logger.info(f"📦 Imported block for timeslot: {block.header.timeslot}")
            logger.info(f'🗳️ Tickets in accumulator: {len(app.state.safrole.ticket_accumulator)}')
        else:
            logger.info(f"🗑 Ignoring block for timeslot: {block.header.timeslot} (current time slot {app.state.timeslot.number}, should produce block: {app.should_produce_block()})")

    return debug_import_block


def create_debug_block_json(app: PyjamazApp, traces_dir: str):
    async def debug_import_block(data):
        logger.debug(f"📦 Importing block from json")
        block = Block.from_json(data)

        if block.header.timeslot > app.state.timeslot.number or (app.state.timeslot.number == 0 and not app.should_produce_block()):

            if traces_dir:
                pre_state = app.state.to_json()

            output = await app.import_block(block)

            if traces_dir:
                await store_trace(pre_state, block, output, app, traces_dir)

            logger.info(f"📦 Imported block for timeslot: {block.header.timeslot}")
            logger.info(f'🗳️ Tickets in accumulator: {len(app.state.safrole.ticket_accumulator)}')
        else:
            logger.info(f"🗑 Ignoring block for timeslot: {block.header.timeslot} (current time slot {app.state.timeslot.number}, should produce block: {app.should_produce_block()})")

    return debug_import_block


@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(package_name='pyjamaz')
@click.option('--seed', type=str,
              default='0x0000000000000000000000000000000000000000000000000000000000000000',
              help='Seed to generate validator keys')
@click.option('--port', type=int, default=9000, show_default=True, help='UDP port on which the validator should run')
@click.option('--ts', type=int, help='Unix timestamp for when the validator starts.')
@click.option('--mode', type=click.Choice(['safrole', 'assurance', 'finality', 'conformance']),
              default='safrole', show_default=True)
@click.option('--culprit', is_flag=True, help="Culprit mode: node will intentionally act malicious")
@click.option('--block-dir', type=click.Path(exists=True))
@click.option('--traces-dir', type=click.Path(exists=True))
@click.option('--db-path', 'custom_db_path', type=click.Path(exists=True))
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--host', 'host', type=str, default="::", show_default=True, help='Host address to listnen on')
@click.option('--certificate', 'certificate', type=str, help='Certificate')
@click.option('--private-key', 'private_key', type=str, help='Private key')
async def main(ctx, seed, port, ts, mode, culprit, block_dir, traces_dir, custom_db_path, verbose, host, certificate, private_key):
    """PyJAMaz: Python JAM Client"""

    # Setup logging
    log_level = logging.DEBUG if verbose else logging.INFO
    setup_logging(log_level)

    if ctx.invoked_subcommand is None:

        if mode != 'safrole':
            raise BadParameter(f'{mode} is not supported yet')

        db_path = custom_db_path or default_db_path

        if not ts:
            # default start ts
            current_time = time.time()
            ts = int(current_time - (current_time % 12) + 12)

        try:
            app = initialize_app(
                keys=Keys.from_seed(bytes.fromhex(seed[2:])),
                custom_db_path=custom_db_path
            )
        except StateKeyNoResult:
            raise BadParameter(f'DB is not yet initialized; run init first')

        logger.info(f'🥋 Starting PyJAMaz client, listening on port {port}')
        logger.info(f'💾 Storage path: {db_path}')
        logger.info(f'🔑 Bandersnatch public: 0x{app.config.keys.bandersnatch.public_key.hex()}')
        logger.info(f'🔑 Ed25519 public: 0x{app.config.keys.ed25519.public_key.hex()}')
        logger.info(f'🗓️ Common Era: {app.config.common_era} ({datetime.fromtimestamp(app.config.common_era).strftime("%Y-%m-%d %H:%M:%S")})')
        logger.info(f'⏱️ Latest timeslot: #{app.state.timeslot.number}')

        logger.info(
            f'💤 Waiting to start at {datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")}'
            )
        await anyio.sleep(ts - time.time())

        lock = anyio.Lock()

        pubsub = PubSub()

        try:
            async with anyio.create_task_group() as tg:

                # Create a subscriber to process incomming messages (fx from a protocol)
                tg.start_soon(pubsub.process_messages)

                if block_dir:
                    logger.info(f"👀 Watching directory: {block_dir} for new blocks...")
                    fs_protocol = FSProtocol(block_dir, traces_dir, lock, pubsub)
                    pubsub.subscribe(MESSAGE_TYPES.PRODUCED_BLOCK, fs_protocol.broadcast_block)
                    pubsub.subscribe(MESSAGE_TYPES.IMPORT_BLOCK_JSON, create_debug_block_json(app, traces_dir))
                    tg.start_soon(fs_protocol.listen)
                else:
                    nps_protocol = JAMNPS(host, port, certificate, private_key, pubsub)
                    pubsub.subscribe(MESSAGE_TYPES.PRODUCED_BLOCK, nps_protocol.broadcast_block)
                    pubsub.subscribe(MESSAGE_TYPES.IMPORT_BLOCK_BYTES, create_debug_block_bytes(app, traces_dir))
                    tg.start_soon(nps_protocol.listen)
                    validator_metadata = [x.metadata for x in app.state.safrole.validators]

                    node_port_hex = validator_metadata[0].hex()
                    node_port = int.from_bytes(bytes.fromhex(node_port_hex[32:36]), 'little')

                    #if node_port != port:
                    for bin_data in validator_metadata:
                        # TODO: create proper encoder/decoder for this..
                        # The validators' IP-layer endpoints are given as IPv6/port combinations,
                        # to be found in the first 18 bytes of validator metadata, with the first 16 bytes being the IPv6 address and
                        # the latter 2 being a little endian representation of the port.
                        hex_data = bin_data.hex()
                        ip_data = bytes.fromhex(hex_data[:32])
                        port_data = bytes.fromhex(hex_data[32:36])
                        validator_address = socket.inet_ntop(socket.AF_INET6, ip_data)
                        validator_port = int.from_bytes(port_data, 'little')
                        if validator_port == port:
                            continue

                        #TODO: for now we hardcode all nodes to be hosted on localhost
                        validator_address = "localhost"
                        tg.start_soon(nps_protocol.connect, validator_address, validator_port)

                    logger.info(f"👀 Watching network for new blocks...")
                    tg.start_soon(network_block_importer, app, block_dir, traces_dir, lock)

                tg.start_soon(timeslot_ticker, app, traces_dir, lock, pubsub)

        except (KeyboardInterrupt, CancelledError):
            logger.info("Stopping node...")
        finally:
            logger.info(f'Node stopped.')


async def store_trace(pre_state: dict, block: Block, output: STFOutput, app: PyjamazApp, traces_dir: str):
    state_diff = DeepDiff(pre_state, app.state.to_json(), ignore_order=True)

    with open(os.path.join(traces_dir, f'state-diff-{block.header.timeslot:06}.json'), 'w') as file:
        json.dump(state_diff, file, indent=2)

    state_data = app.state.to_json()

    with open(os.path.join(traces_dir, f'state-{block.header.timeslot:06}.json'), 'w') as file:
        json.dump(state_data, file, indent=2)

    with open(os.path.join(traces_dir, f'block-{block.header.timeslot:06}.json'), 'w') as file:
        json.dump(block.to_json(), file, indent=2)


async def network_block_importer(app: PyjamazApp,  protocol, traces_dir, lock):
    pass



async def timeslot_ticker(app: PyjamazApp, traces_dir, lock, pubsub: PubSub):

    while True:
        timeslot = app.current_timeslot()

        if app.state.timeslot.number >= timeslot:
            logger.debug('⚠️ Timeslot did not advance; yield for 0.1 seconds')
            await anyio.sleep(0.1)
            continue

        await app.process_timeslot(timeslot)

        if app.should_produce_block():

            async with lock:
                try:

                    if traces_dir:
                        pre_state = app.state.to_json()

                    block = await app.produce_block(timeslot)

                    if traces_dir:
                        await store_trace(pre_state, block, None, app, traces_dir)

                    if pubsub:
                        pubsub.send_stream.send_nowait({"message_type": MESSAGE_TYPES.PRODUCED_BLOCK, "data": block})

                    logger.info(f'🎁 Produced block for #{block.header.timeslot} | hash: 0x{block.header.hash.hex()}')
                except Exception as e:
                    raise
                    logger.info(f'🗑️ Discarded produced block for #{timeslot}: {e}')
                    # Rollback state from DB
                    app.state = app.retrieve_jam_state()
                    # TODO Make transactional
                    app.extrinsic.clear_tickets()

        else:
            logger.info(f'💤 Waiting for block #{app.current_timeslot()} | epoch #{app.current_epoch()} | phase #{app.current_slot_phase_index()}')

        await anyio.sleep(app.get_next_slot_timestamp() - time.time() + 0.01)


@main.group()
async def keys():
    """
    Manage validator keys
    """
    pass


@keys.command()
@click.argument('seed', type=str)
def generate(seed):
    """
    Generate serialized validator data for given SEED
    """

    validator_keys = Keys.from_seed(bytes.fromhex(seed[2:]))

    key_data = {
        "bandersnatch": f"0x{validator_keys.bandersnatch.public_key.hex()}",
        "ed25519": f"0x{validator_keys.ed25519.public_key.hex()}",
        "bls": f"0x{bytes(144).hex()}",
        "bandersnatch_priv": f"0x{validator_keys.bandersnatch.private_key.hex()}",
        "ed25519_priv": f"0x{validator_keys.ed25519.private_key.hex()}",
        "bls_priv": f"0x{bytes(32).hex()}",
    }

    click.echo(json.dumps(key_data, indent=2))


@main.command()
@click.option('--initial-state', type=click.Path(exists=True))
@click.option('--genesis', type=click.Path())
@click.option('--db-path', 'custom_db_path', type=click.Path())
@click.option('--force-overwrite', is_flag=True, help="Skip confirmation to overwrite existing database")
@click.option('--cert-seed', 'cert_seed', type=str)
@click.option('--cert-file', 'cert_file', type=str)
@click.option('--cert-pk-file', 'cert_pk_file', type=str)
@click.option('--cert-ips', 'cert_ips', default="::", type=str)
@click.option('--cert-domains', 'cert_domains', type=str)
@click.option('--cert-country', 'cert_country', default="US", type=str)
@click.option('--cert-state', 'cert_state', default="test state", type=str)
@click.option('--cert-city', 'cert_city', default="test city", type=str)
@click.option('--cert-organization', 'cert_organization', default="test", type=str)
@click.option('--cert-website', 'cert_website', default="test.com", type=str)
async def init(
        initial_state,
        genesis,
        custom_db_path,
        force_overwrite,
        cert_seed,
        cert_file,
        cert_pk_file,
        cert_ips,
        cert_domains,
        cert_country,
        cert_state,
        cert_city,
        cert_organization,
        cert_website,
):
    """
    Clears all existing data and initializes the JAM client.

    Defaults to DEV initial state if none is provided.
    """

    db_path = custom_db_path or default_db_path
    common_era = None

    if os.path.isdir(db_path):
        if not force_overwrite:
            click.confirm(f"Database already exists at '{db_path}', delete?", abort=True)
        shutil.rmtree(db_path)  # Delete the directory if it exists
        click.echo(f"The database at '{db_path}' was deleted successfully.")

    if initial_state is not None:

        if initial_state.endswith('.json'):
            with open(initial_state, 'r') as fp:
                state_data = json.load(fp)
            jam_state = JamState.from_json(state_data)

        elif initial_state.endswith('.bin'):
            with open(initial_state, 'rb') as fp:
                jam_state = JamState.from_jam_bytes(JamBytes(fp.read()))

        else:
            raise BadParameter('initial_state can only be .json or .bin')
    else:
        if genesis is None:
            genesis = path.join(data_dir,  'genesis.json')

        with open(genesis, 'r') as fp:
            genesis_data = json.load(fp)
            common_era = genesis_data['common_era']
            jam_state = JamState.create_genesis_state(
                validators=[ValidatorData.from_json(v) for v in genesis_data['validators']],
            )

    app = initialize_app(read_state=False, custom_db_path=custom_db_path, common_era=common_era)
    app.store_jam_state(jam_state)

    keys = Keys.from_seed(bytes.fromhex(cert_seed))

    pk_pem, cert_pem = generate_cert(
        keys,
        cert_ips,
        cert_domains,
        cert_country,
        cert_state,
        cert_city,
        cert_organization,
        cert_website,
    )

    write_cert(pk_pem, cert_pk_file, cert_pem, cert_file)

    click.echo(f"✅ Initialization complete.")


@main.command('dump')
@click.option(
    '--format', 'output_format',
    type=click.Choice(['json', 'bin'], case_sensitive=False),
    default='json',
    show_default=True,
    help='Choose the output format: JSON or JAM-bytes'
)
async def dump_state(output_format):
    """
    Dumps current state to stdout

    """
    app = initialize_app()

    if output_format == 'json':
        click.echo(json.dumps(app.state.to_json(), indent=2))
    elif output_format == 'bin':
        click.echo(app.state.to_jam_bytes().to_bytes(), file=click.get_binary_stream('stdout'), nl=False)


if __name__ == '__main__':
    main(_anyio_backend="asyncio")
