import asyncio
import logging
from asyncio import CancelledError
from datetime import datetime
import json
import os
import shutil
import socket

import anyio

import time
from os import path

import asyncclick as click
from asyncclick import BadParameter
from deepdiff import DeepDiff

from jamcodec.base import JamBytes
from pyjamaz.app import PyjamazApp, AppConfig, Keys
from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.graypaper_constants import COMMON_ERA, EPOCH_TIMESLOTS
from pyjamaz.logger import setup_logging
from pyjamaz.models.stf_output import STFOutput
from pyjamaz.storage import LevelDBStorage, InMemoryStorage
from pyjamaz.models.block import Block, Header
from pyjamaz.models.state import JamState
from pyjamaz.transport.generate_cert import generate_cert, write_cert
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

    if common_era < 10000:
        # epoch is relative to current time
        current_time = time.time()
        common_era = int(current_time - (current_time % common_era) + common_era)

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

def broadcast_block_to_file(block_dir):
    def broadcast(block):
        # write block to dir
        filepath = os.path.join(block_dir, f'block-{block.header.timeslot:06}.json')
        with open(filepath, 'w') as file:
            json.dump(block.to_json(), file, indent=2)

    return broadcast


def broadcast_block_to_network(protocol):
    async def broadcast(block):
        print("BROADCASTING!!!!!!!!")

        await protocol.broadcast_block_announcement(block)

    return broadcast


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

        try:
            app = initialize_app(
                keys=Keys.from_seed(bytes.fromhex(seed[2:])),
                common_era=ts,
                custom_db_path=custom_db_path
            )
        except StateKeyNoResult:
            raise BadParameter(f'DB is not yet initialized; run init first')

        logger.info(f'🥋 Starting PyJAMaz client, listening on port {port}')
        logger.info(f'💾 Storage path: {db_path}')
        logger.info(f'🔑 Bandersnatch public: 0x{app.config.keys.bandersnatch.public_key.hex()}')
        logger.info(f'🔑 Ed25519 public: 0x{app.config.keys.ed25519.public_key.hex()}')
        logger.info(f'🗓️ Common Era: {app.config.common_era}')
        logger.info(f'⏱️ Latest timeslot: #{app.state.timeslot.number}')

        lock = anyio.Lock()

        try:
            async with anyio.create_task_group() as tg:
                if block_dir:
                    # TODO schedule to start at 0ms of clock
                    tg.start_soon(timeslot_ticker, app, traces_dir, lock, broadcast_block_to_file(block_dir))
                    logger.info(f"👀 Watching directory: {block_dir} for new blocks...")
                    tg.start_soon(file_block_importer, app, block_dir, traces_dir, lock)
                else:
                    print("LISTNEN: ", host, port)
                    protocol = JAMNPS(host, port, certificate, private_key)
                    asyncio.create_task(protocol.listen())
                    validator_metadata = [x.metadata for x in app.state.safrole.validators]
                    for bin_data in validator_metadata:
                        #TODO: ook een encoder/decoder voor maken? scale?
                        hex_data = bin_data.hex()
                        ip_data = bytes.fromhex(hex_data[:32])
                        port_data = bytes.fromhex(hex_data[32:36])
                        validator_address = socket.inet_ntop(socket.AF_INET6, ip_data)
                        validator_port = int.from_bytes(port_data, 'little')
                        #TODO: temp hack to connect to everyone but ourselves
                        if validator_port != port:
                            #if validator_port in (9000,):
                                #print("TRY TO CONNECT TO : ", validator_address, validator_port)
                                #asyncio.create_task(protocol.connect(validator_address, validator_port))
                                #print("TRY TO CONNECT TO : ", host, validator_port)
                            validator_address = host #TODO: fix certs for ipv6
                            asyncio.create_task(protocol.connect(validator_address, validator_port))

                    """
                    app.state.safrole.validators[0].metadata
                        hex_str = socket.inet_pton(socket.AF_INET6, "::").hex() + (9000).to_bytes(2, byteorder='little').hex()
                        ip_bytes = bytes.fromhex(hex_str[:32])
                        
                        ip_bytes = bytes.fromhex(hex_str[:32])
                        
                        port_bytes = bytes.fromhex(hex_str[32:])
                        ipv6_address = socket.inet_ntop(socket.AF_INET6, ip_bytes.hex())
                        ipv6_port = int.from_bytes(port_bytes, 'little')
                    
                    send_block_announcement(block.to_jam_bytes().to_bytes())
                    
                    event raisen vanuit protocol -> met binaire data
                        Block.from_jam_bytes(JamBytes(byte_data))
                    
                    The validators' IP-layer endpoints are given as IPv6/port combinations, to be found in the first 18 bytes of validator metadata, with the first 16 bytes being the IPv6 address and the latter 2 being a little endian representation of the port.
                    """

                    tg.start_soon(timeslot_ticker, app, traces_dir, lock, broadcast_block_to_network(protocol))
                    logger.info(f"👀 Watching network for new blocks...")
                    tg.start_soon(network_block_importer, app, block_dir, traces_dir, lock)

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


async def file_block_importer(app: PyjamazApp, block_dir, traces_dir, lock):

    seen_files = set()

    while True:
        # Run the directory check in a separate thread (non-blocking)
        new_files = await anyio.to_thread.run_sync(
            lambda: {f for f in os.listdir(block_dir) if f.startswith('block-')} - seen_files
        )

        if new_files:
            for filename in sorted(new_files):
                filepath = os.path.join(block_dir, filename)

                try:
                    async with lock:
                        with open(filepath, 'r') as file:

                            data = json.load(file)
                            # TODO also import .bin jamcodec files
                            block = Block.from_json(data)

                            # TODO block.header.timeslot == 0 possible?
                            if block.header.timeslot > app.state.timeslot.number or (app.state.timeslot.number == 0 and not app.should_produce_block()):

                                # # TODO move to app.process_timeslot()
                                # if app.is_epoch_change():
                                #     logging.info("🗓️ Process Epoch change")
                                #     # Process tickets
                                #     app.extrinsic.on_epoch_change()
                                #     logging.info(
                                #         f"🎫 Current tickets {[i.hex() for i in app.extrinsic.own_tickets_current]}"
                                #         )

                                if traces_dir:
                                    pre_state = app.state.to_json()

                                output = await app.import_block(block)

                                if traces_dir:
                                    await store_trace(pre_state, block, output, app, traces_dir)

                                logger.info(f"📦 Imported: {os.path.basename(filepath)}")
                                logger.info(f'🎫 Collected tickets: {len(app.state.safrole.ticket_accumulator)}')
                            else:
                                logger.info(f"⏭️ Skipped: {os.path.basename(filepath)}")

                except Exception as e:
                    logger.error(f"Failed to process {filepath}: {e}")

            # Update the seen_files set to include the newly processed files
            seen_files.update(new_files)

        await anyio.sleep(.5)


async def timeslot_ticker(app: PyjamazApp, traces_dir, lock, broadcaster):

    logger.info(f'💤 Waiting to start at {datetime.fromtimestamp(app.config.common_era).strftime("%Y-%m-%d %H:%M:%S")}')
    await anyio.sleep(app.config.common_era - time.time())

    while True:
        timeslot = app.current_timeslot()

        # TODO !! temporary to determine if first block in new epoch should be produced. Cannot be determined without
        #  triggering state changes in STFs caused be epoch change.
        if app.is_epoch_change(timeslot):
            # TODO move to app.on_epoch_change()
            app.latest_epoch = timeslot // EPOCH_TIMESLOTS
            logging.info("🗓️ Process Epoch change")

            header = Header.default()
            header.timeslot = timeslot
            post_safrole_state = app.components.safrole.state_transition(
                header=header,
                pre_state_timeslot=app.state.timeslot,
                pre_state_safrole=app.state.safrole,
                pre_state_validator_queue=app.state.validator_queue,
                post_state_entropy=app.state.entropy,
                post_state_disputes=app.state.disputes,
                post_state_validator_pool=app.state.validator_pool,
                extrinsic_tickets=[]
            )
            # Update slot_sealer_series in advance
            app.state.safrole.slot_sealer_series = post_safrole_state.post_state.slot_sealer_series
            logging.debug(f'New slot_sealer_series: {app.state.safrole.slot_sealer_series.to_json()}')
            # Process tickets
            app.extrinsic.on_epoch_change()
            logging.debug(f"Current tickets {[i.hex() for i in app.extrinsic.own_tickets_current]}")

        if app.should_produce_block():

            async with lock:
                try:

                    if traces_dir:
                        pre_state = app.state.to_json()

                    block = await app.produce_block(timeslot)

                    if traces_dir:
                        await store_trace(pre_state, block, None, app, traces_dir)

                    if broadcaster:
                        await broadcaster(block)

                    logger.info(f'🎁 Produced block: #{block.header.timeslot}')
                except Exception as e:
                    raise
                    logger.info(f'🗑️ Discarded produced block for #{timeslot}: {e}')
                    # Rollback state from DB
                    app.state = app.retrieve_jam_state()
                    # TODO Make transactional
                    app.extrinsic.clear_tickets()

        else:
            logger.info(f'💤 Waiting for block #{app.current_timeslot()} | epoch #{app.current_epoch()} | phase #{app.current_slot_phase_index()}')

        await anyio.sleep(app.get_next_slot_timestamp() - time.time())


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

    if os.path.isdir(db_path):
        if not force_overwrite:
            click.confirm(f"Database already exists at '{db_path}', delete?", abort=True)
        shutil.rmtree(db_path)  # Delete the directory if it exists
        click.echo(f"The database at '{db_path}' was deleted successfully.")

    if initial_state is None:
        initial_state = path.join(data_dir, 'initial_state_template.json')

    if initial_state.endswith('.json'):
        with open(initial_state, 'r') as fp:
            state_data = json.load(fp)
        jam_state = JamState.from_json(state_data)

    elif initial_state.endswith('.bin'):
        with open(initial_state, 'rb') as fp:
            jam_state = JamState.from_jam_bytes(JamBytes(fp.read()))

    else:
        raise BadParameter('initial_state can only be .json or .bin')

    app = initialize_app(read_state=False, custom_db_path=custom_db_path)
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
