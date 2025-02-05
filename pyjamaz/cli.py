import logging
from asyncio import CancelledError
from datetime import datetime
import json
import os
import shutil
import socket
from doctest import debug
from uuid import bytes_

import anyio
import ipaddress
import time
from os import path

import asyncclick as click
from asyncclick import BadParameter, MissingParameter
from deepdiff import DeepDiff

from jamcodec.base import JamBytes

from pyjamaz.app import PyjamazApp, AppConfig, Keys
from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.graypaper_constants import COMMON_ERA, EPOCH_TIMESLOTS
from pyjamaz.logger import setup_logging
from pyjamaz.models.common import ValidatorData
from pyjamaz.models.trace import Trace
from pyjamaz.storage import LevelDBStorage, InMemoryStorage, TransactionRolledBack
from pyjamaz.models.block import Block, Header
from pyjamaz.models.state import JamState
from pyjamaz.transport.cert import generate_cert, write_cert
from pyjamaz.transport.protocol_fs import FSProtocol
from pyjamaz.transport.protocol_jamnp_s import JAMNPS
from pyjamaz.transport.pubsub import PubSub
from pyjamaz.utils import format_hash

data_dir = path.join(path.dirname(path.abspath(__file__)), 'data')
default_db_path = path.join(data_dir, 'db')


def ipv6_to_byte_array(ip_str:str) -> bytearray:
    """
    Converts an IPv4 or IPv6 string into a byte array.

    Args:
        ip_str (str): The IP address as a string.

    Returns:
        tuple: A tuple containing a byte array representing the IP address and the zone index (if present).

    Raises:
        ValueError: If the input is not a valid IP address.
    """
    try:
        if ":" in ip_str:  # Likely an IPv6 address
            ip = ipaddress.IPv6Address(ip_str.split('%')[0])
            zone = ip_str.split('%')[1] if '%' in ip_str else None
            return bytearray(ip.packed), zone
        else:  # Likely an IPv4 address
            ip = ipaddress.IPv4Address(ip_str)
            return bytearray(ip.packed), None
    except ipaddress.AddressValueError:
        raise ValueError(f"Invalid IP: {ip_str}")


def wrap_cli_import_block(traces_dir, validate=True):
    async def cli_import_block(self, block: Block, validate=validate):
        if block.header.timeslot > self.state.timeslot.number or (
                self.state.timeslot.number == 0 and not self.should_produce_block()):

            if traces_dir:
                pre_state = await self.create_state_dump()

            await self._import_block(block, validate)

            if traces_dir:
                await self.store_trace(pre_state, block, traces_dir)

            logging.info(f"📦 Imported block for timeslot: {block.header.timeslot}")
            logging.info(f'🗳️ Tickets in accumulator: {len(self.state.safrole.ticket_accumulator)}')
        else:
            logging.info(
                f"🗑 Ignoring block for timeslot: {block.header.timeslot} (current time slot {self.state.timeslot.number}, should produce block: {self.should_produce_block()})")

    return cli_import_block


def wrap_produced_block_jamnp(app: PyjamazApp, traces_dir, np_protocol: JAMNPS):
    async def produced_block_jamnp(block: Block):
        await app.import_block(block)
        await np_protocol.broadcast_block(block)

    return produced_block_jamnp


def wrap_produced_block_fs(app: PyjamazApp, traces_dir, fs_protocol: FSProtocol):
    async def produced_block_fs(block: Block):
        await app.import_block(block)
        await fs_protocol.broadcast_block(block)

    return produced_block_fs


async def initialize_app(
        read_state=True,
        memory_storage=False,
        keys=None,
        common_era=None,
        custom_db_path=None,
        record_traces=None
) -> PyjamazApp:

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
        logging.error(f'Could not initialize storage engine: {str(e)}')
        exit(2)

    # Set common era
    if not common_era:
        common_era = COMMON_ERA

    # Initialize app
    config = AppConfig(
        ring_data=ring_data,
        storage_engine=storage_engine,
        keys=keys,
        common_era=common_era,
        create_traces=record_traces
    )

    app = PyjamazApp(config=config, import_block_callback=wrap_cli_import_block(record_traces))

    if read_state:
        await app.initialize()

    return app


# CLI commands

@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(package_name='pyjamaz')
@click.option('--seed', type=str,
              help='Seed to generate validator keys')
@click.option('--port', type=int, default=9000, show_default=True, help='UDP port on which the validator should run')
@click.option('--ts', type=int, help='Unix timestamp for when the validator starts.')
@click.option('--mode', type=click.Choice(['safrole', 'assurance', 'finality', 'conformance']),
              default='safrole', show_default=True)
@click.option('--culprit', is_flag=True, help="Culprit mode: node will intentionally act malicious")
@click.option('--block-dir', type=click.Path(exists=True))
@click.option('--record-traces', type=click.Path(exists=True))
@click.option('--db-path', 'custom_db_path', type=click.Path(exists=True))
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--host', 'host', type=str, default="127.0.0.1", show_default=True, help='Host address to listnen on')
async def main(ctx, seed, port, ts, mode, culprit, block_dir, record_traces, custom_db_path, verbose, host):
    """PyJAMaz: Python JAM Client"""

    # Note: Add packages that need a different logging level here
    log_package_overrides = {
        #"pyjamaz.transport": logging.DEBUG
        "quic": logging.WARNING,
    }

    # Setup logging
    log_level = logging.DEBUG if verbose else logging.INFO
    setup_logging(log_level, log_package_overrides)

    if ctx.invoked_subcommand is None:

        if seed is None:
            raise MissingParameter("--seed parameter is required")
        elif not seed.startswith("0x") or len(seed) != 66:
            raise BadParameter("Seed should start with '0x' and have a length of 66 chars")

        if mode != 'safrole':
            raise BadParameter(f'{mode} is not supported yet')

        db_path = custom_db_path or default_db_path

        network_bootstrap = ts is None
        if network_bootstrap:
            ts = 0

        #TODO: currently it is not possible to provide a hard unix timestamp (only deltas)
        current_time = time.time()
        ts = (current_time // 6) * 6 + ts

        try:
            app = await initialize_app(
                keys=Keys.from_seed(bytes.fromhex(seed[2:])),
                custom_db_path=custom_db_path,
                record_traces=record_traces
            )
        except StateKeyNoResult:
            raise BadParameter(f'DB is not yet initialized; run init first')

        app.network_bootstrap = network_bootstrap

        logging.info(f'🥋 Starting PyJAMaz client, listening on port {port}')
        logging.info(f'💾 Storage path: {db_path}')
        logging.info(f'🔑 Bandersnatch public: 0x{app.config.keys.bandersnatch.public_key.hex()}')
        logging.info(f'🔑 Ed25519 public: 0x{app.config.keys.ed25519.public_key.hex()}')
        logging.info(f'🗓️ Common Era: {app.config.common_era} ({datetime.fromtimestamp(app.config.common_era).strftime("%Y-%m-%d %H:%M:%S")})')
        logging.info(f'🌲 State trie root: 0x{app.state_trie_root.hex()}')
        logging.info(f'⏱️ Latest timeslot: #{app.state.timeslot.number}')

        logging.info(
            f'💤 Waiting to start at {datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")}'
            )

        pubsub = PubSub()

        try:
            async with anyio.create_task_group() as tg:

                # Create a subscriber to process incomming messages (fx from a protocol)
                tg.start_soon(pubsub.process_messages)

                if block_dir:
                    logging.info(f"👀 Watching directory: {block_dir} for new blocks...")
                    fs_protocol = FSProtocol(block_dir, pubsub, app)
                    app.protocol = fs_protocol
                    pubsub.subscribe(MESSAGE_TYPES.PRODUCED_BLOCK, wrap_produced_block_fs(app, record_traces, fs_protocol))
                    pubsub.subscribe(MESSAGE_TYPES.RECEIVED_BLOCK, app.import_block_from_json)
                    pubsub.subscribe(MESSAGE_TYPES.REQUESTED_BLOCKS, app.requested_blocks_from_json)
                    tg.start_soon(fs_protocol.listen)
                else:
                    certificate_file = os.path.join(db_path, "cert.pem")
                    pk_file = os.path.join(db_path, "cert.key")
                    nps_protocol = JAMNPS(host, port, certificate_file, pk_file, pubsub, app)
                    app.protocol = nps_protocol
                    pubsub.subscribe(MESSAGE_TYPES.PRODUCED_BLOCK, wrap_produced_block_jamnp(app, record_traces, nps_protocol))
                    pubsub.subscribe(MESSAGE_TYPES.RECEIVED_BLOCK, app.import_block_from_bytes)
                    pubsub.subscribe(MESSAGE_TYPES.REQUESTED_BLOCKS, app.requested_blocks_from_bytes)
                    tg.start_soon(nps_protocol.listen)
                    #validator_metadata = [x.metadata for x in app.state.safrole.validators]

                    #node_port_hex = validator_metadata[0].hex()
                    #node_port = int.from_bytes(bytes.fromhex(node_port_hex[32:36]), 'little')

                    #if node_port != port:
                    for validator in app.state.safrole.validators:
                        # TODO: create proper encoder/decoder for this..
                        # The validators' IP-layer endpoints are given as IPv6/port combinations,
                        # to be found in the first 18 bytes of validator metadata, with the first 16 bytes being the IPv6 address and
                        # the latter 2 being a little endian representation of the port.
                        bytes_data = validator.metadata
                        validator_port = int.from_bytes(bytes_data[16:18], byteorder='little')
                        if bytes_data[4:16] == bytes(12):
                            validator_address = str(ipaddress.IPv4Address(bytes(bytes_data[:4])))
                        else:
                            #TODO: FIX: validator_address = socket.inet_ntop(socket.AF_INET6, ip_data)
                            validator_address = socket.inet_ntop(socket.AF_INET6, bytes_data[:16]) #str(ipaddress.IPv6Address(bytes_data[:16]))

                        if validator.ed25519 == app.config.keys.ed25519.public_key:
                            logging.debug(
                                f'Skipping own node ({validator_address}:{validator_port})'
                            )
                            continue

                        #TODO: for now we hardcode all nodes to be hosted on localhost
                        #validator_address = "localhost"
                        logging.info(
                            f'Connecting to node {validator_address}:{validator_port}'
                        )
                        tg.start_soon(nps_protocol.connect, validator_address, validator_port)

                await anyio.sleep(ts - time.time())
                tg.start_soon(timeslot_ticker, app, pubsub)
        except (KeyboardInterrupt, CancelledError):
            logging.info("Stopping node...")
        finally:
            logging.info(f'Node stopped.')


async def timeslot_ticker(app: PyjamazApp, pubsub: PubSub):

    while True:
        # TODO centralize
        app.block_context.reset()
        timeslot = app.current_timeslot()
        logging.info(f"⏳️ Timeslot: {timeslot}")

        if app.state.timeslot.number >= timeslot:
            logging.debug('⚠️ Timeslot did not advance; yield for 0.1 seconds')
            await anyio.sleep(0.1)
            continue

        if app.is_epoch_change(timeslot):
            app.latest_epoch = timeslot // EPOCH_TIMESLOTS
            logging.info("🗓️ Process Epoch change")

            # TODO !! temporary to determine if first block in new epoch should be produced. Cannot be determined without
            #  triggering state changes in STFs caused be epoch change.

            header = Header.default()
            header.timeslot = timeslot

            entropy_output = app.components.entropy.state_transition(
                header=header,
                pre_state_timeslot=app.state.timeslot,
                pre_state_entropy=app.state.entropy
            )

            safrole_output = app.components.safrole.state_transition(
                header=header,
                pre_state_timeslot=app.state.timeslot,
                pre_state_safrole=app.state.safrole,
                pre_state_validator_queue=app.state.validator_queue,
                post_state_entropy=entropy_output.post_state,
                post_state_disputes=app.state.disputes,
                post_state_validator_pool=app.state.validator_pool,
                extrinsic_tickets=[]
            )

            # Process tickets
            app.extrinsic.process_epoch_change()
            logging.debug(f"Current tickets {[i.hex() for i in app.extrinsic.own_tickets_current]}")

            safrole_state = safrole_output.post_state
            entropy_state = entropy_output.post_state
        else:
            safrole_state = app.state.safrole
            entropy_state = app.state.entropy

        if app.should_produce_block(safrole_state):

            try:

                block = await app.produce_block(timeslot, safrole_state, entropy_state)

                pubsub.send_stream.send_nowait({
                    "message_type": MESSAGE_TYPES.PRODUCED_BLOCK,
                    "data": block
                 })

                logging.info(f'🎁 Produced block for #{block.header.timeslot} | hash: 0x{format_hash(block.header.hash)} | epoch #{app.current_epoch()} | phase #{app.current_slot_phase_index()}')
            except Exception as e:
                logging.info(f'🗑️ Discarded produced block for #{timeslot}: {e}')
                # Rollback state from DB
                app.state = app.retrieve_jam_state()
                # TODO Make transactional
                app.extrinsic.clear_tickets()

        else:
            logging.info(f'💤 Waiting for block #{app.current_timeslot()} | epoch #{app.current_epoch()} | phase #{app.current_slot_phase_index()}')

        await anyio.sleep(app.get_next_slot_timestamp() - time.time() + 0.01) #TODO: create constant to give meaning to this number


@main.group()
async def keys():
    """
    Manage validator keys
    """
    pass


@keys.command()
@click.argument('seed', type=str)
@click.argument('ip', type=str)
@click.argument('port', type=int)
def generate(seed, ip, port):
    """
    Generate serialized validator data for given SEED
    """

    validator_keys = Keys.from_seed(bytes.fromhex(seed[2:]))
    metadata = bytearray(128)
    enc, zone = ipv6_to_byte_array(ip)
    if len(enc) == 4:
        metadata[0:4] = enc
    elif len(enc) == 16:
        metadata[0:16] = enc
    else:
        raise Exception("Invalid IP")

    metadata[16:18] = int(port).to_bytes(2, 'little')

    key_data = {
        "bandersnatch": f"0x{validator_keys.bandersnatch.public_key.hex()}",
        "ed25519": f"0x{validator_keys.ed25519.public_key.hex()}",
        "bls": f"0x{bytes(144).hex()}",
        "metadata": f"0x{metadata.hex()}",
    }

    click.echo(json.dumps(key_data, indent=2))


async def init_certificate(db_path, seed):
    keys = Keys.from_seed(bytes.fromhex(seed[2:]))

    pk_pem, cert_pem = generate_cert(
        keys,
        ips="0.0.0.0",
        domains="test.com",
        country="US",
        state="CA",
        city="LA",
        organization="Test Corp",
        website="test.com",
    )
    pk_file = os.path.join(db_path, "cert.key")
    pem_file = os.path.join(db_path, "cert.pem")
    write_cert(pk_pem, pk_file, cert_pem, pem_file)


@main.command()
@click.option('--initial-state', type=click.Path(exists=True))
@click.option('--genesis', type=click.Path(exists=True))
@click.option('--db-path', 'custom_db_path', type=click.Path())
@click.option('--force-overwrite', is_flag=True, help="Skip confirmation to overwrite existing database")
@click.option('--seed', 'seed', type=str, help="Seed to use for validator keys")
async def init(
        initial_state,
        genesis,
        custom_db_path,
        force_overwrite,
        seed
):
    """
    Clears all existing data and initializes the JAM client.

    Defaults to DEV initial state if none is provided.
    """

    if seed is None:
        raise MissingParameter("--seed parameter is required")
    elif not seed.startswith("0x") or len(seed) != 66:
        raise BadParameter("Seed should start with '0x' and have a length of 66 chars")

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

    app = await initialize_app(read_state=False, custom_db_path=custom_db_path, common_era=common_era)
    await app.store_jam_state(jam_state)

    await init_certificate(db_path, seed)

    click.echo(f"✅ Initialization complete.")


@main.command('replay_traces')
@click.argument('traces_dir', type=click.Path(exists=True))
@click.option('--db-path', 'custom_db_path', type=click.Path())
@click.option('--force-overwrite', is_flag=True, help="Skip confirmation to overwrite existing database")
@click.option('--skip-block-validation', is_flag=True, help="Skip block validation before import")
@click.option('--only-block-import', is_flag=True, help="Only import block data and no import of pre-state")
@click.option(
    '--format', 'trace_format',
    type=click.Choice(['pyjamaz', 'duna'], case_sensitive=False),
    default='pyjamaz',
    show_default=True,
    help='Choose the source format of the trace data'
)
@click.option('--seed', 'seed', type=str, help="Seed to use for validator keys")
async def replay_traces(
        traces_dir, custom_db_path, force_overwrite, skip_block_validation, only_block_import, trace_format, seed
):
    if seed is None:
        raise MissingParameter("--seed parameter is required")
    elif not seed.startswith("0x") or len(seed) != 66:
        raise BadParameter("Seed should start with '0x' and have a length of 66 chars")

    # Flush database and import genesis state
    db_path = custom_db_path or default_db_path
    if os.path.isdir(db_path):
        if not force_overwrite:
            click.confirm(f"Database already exists at '{db_path}', delete?", abort=True)
        shutil.rmtree(db_path)  # Delete the directory if it exists
        logging.info(f"The database at '{db_path}' was deleted successfully.")

    os.makedirs(db_path, exist_ok=True)
    if not os.path.isfile(os.path.join(db_path, "cert.key")) or force_overwrite:
        await init_certificate(db_path, seed)

    app = await initialize_app(read_state=False, custom_db_path=custom_db_path)

    traces_files = await anyio.to_thread.run_sync(
        lambda: sorted({f for f in os.listdir(traces_dir) if f.endswith('.bin')})
    )

    for block_file in traces_files:
        logger.info(f'📂 Processing trace file {block_file}')
        with open(os.path.join(traces_dir, block_file), 'rb') as fp:
            trace = Trace.from_jam_bytes(JamBytes(fp.read()))

        if not only_block_import or app.state_trie_root == bytes(32):

            for k, v, name, metadata in trace.pre_state.keyvals:
                app.state_db.put(bytes(k), bytes(v))

            app.state = app.retrieve_jam_state()
            await app.update_state_trie()
            app.latest_epoch = app.state.timeslot.epoch_number()

            assert app.state_trie_root == trace.pre_state.state_root
            logging.info(f'🎬 Genesis succesfully saved (state root: 0x{app.state_trie_root.hex()})')

        logging.info(f'⚙️ Processing block {trace.block.header.timeslot} (hash: 0x{trace.block.header.hash.hex()})..')
        try:
            await app.import_block(trace.block, dry_run=not skip_block_validation)
            logging.info(f'✅ Block {trace.block.header.timeslot} succesfully imported.')

        except TransactionRolledBack as e:
            logging.error(f'Failed to import block {trace.block.header.timeslot}: {e}')
            break

        if not only_block_import:

            if app.state_trie_root == trace.post_state.state_root:
                logging.info(f'✅ State trie root matches (0x{trace.post_state.state_root.hex()})')
            else:
                logging.error(f'State root of trace {trace.post_state.state_root.hex()} does not match with current state {app.state_trie_root.hex()}')
                logging.info('Dumping state differences:')
                actual_state = app.state.to_json()

                for k, v, name, metadata in trace.post_state.keyvals:
                    app.state_db.put(bytes(k), bytes(v))

                app.state = app.retrieve_jam_state()

                state_diff = DeepDiff(app.state.to_json(), actual_state, ignore_order=True)
                if state_diff:
                    click.echo(json.dumps(state_diff, indent=2))
                    response = click.prompt("Press Enter to continue or type 'q' to quit", default='', show_default=False)
                    if response.lower() == 'q':
                        logging.info('✋ User aborted.')
                        break


@main.command('dump_state')
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
    app = await initialize_app()

    if output_format == 'json':
        click.echo(json.dumps(app.state.to_json(), indent=2))
    elif output_format == 'bin':
        click.echo(app.state.to_jam_bytes().to_bytes(), file=click.get_binary_stream('stdout'), nl=False)


@main.command('dump_block')
@click.argument('timeslot', type=int)
@click.option(
    '--format', 'output_format',
    type=click.Choice(['json', 'bin'], case_sensitive=False),
    default='json',
    show_default=True,
    help='Choose the output format: JSON or JAM-bytes'
)
async def dump_block(timeslot, output_format):
    """
    Dumps current state to stdout

    """
    app = await initialize_app()

    block = app.block_db.get(b'block:' + timeslot.to_bytes(length=4, byteorder='little'))

    if block is None:
        click.echo('Block not found', err=True)
    else:
        if output_format == 'json':
            click.echo(json.dumps(Block.from_jam_bytes(JamBytes(block)).to_json(), indent=2))
        elif output_format == 'bin':
            click.echo(block, file=click.get_binary_stream('stdout'), nl=False)


if __name__ == '__main__':
    main(_anyio_backend="asyncio")
