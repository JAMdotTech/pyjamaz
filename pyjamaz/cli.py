import asyncio
import logging
import re
import traceback
from asyncio import CancelledError
from datetime import datetime
import json
import os
import shutil

import anyio
import ipaddress
import time
from os import path

import asyncclick as click
from asyncclick import BadParameter, MissingParameter

from jamcodec.base import JamBytes

from pyjamaz.app import PyjamazApp, AppConfig, Keys
from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.graypaper_constants import COMMON_ERA, EPOCH_TIMESLOTS
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.logger import setup_logging
from pyjamaz.models.common import ValidatorData
from pyjamaz.models.app import Trace, StateDump, ChainspecDump
from pyjamaz.rpc.ws_server import start_rpc_server, WebSocketServer
from pyjamaz.settings import GP_VERSION, SOLO_MODE
from pyjamaz.state.base import state_key_constructor_service_account, state_key_constructor_preimage, \
    state_key_constructor_preimage_availability
from pyjamaz.storage import LevelDBStorage, InMemoryStorage, TransactionRolledBack
from pyjamaz.models.block import Block, Header, Extrinsic
from pyjamaz.models.state import JamState, ServiceAccount, ServiceActivityRecord
from pyjamaz.transport.cert import generate_cert, write_cert
from pyjamaz.transport.protocol_fs import FSProtocol
from pyjamaz.transport.protocol_jamnp_s import JAMNPS

from pyjamaz.transport.pubsub import PubSub, PubSubSignal
from pyjamaz.utils import format_hash, quic_peer_id

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


def wrap_cli_import_block(traces_dir):
    async def cli_import_block(self, block: Block, dry_run=False):

        if traces_dir:
            pre_state = await self.create_state_dump()

        try:
            await self._import_block(block, dry_run=dry_run)

            if traces_dir:
                await self.store_trace(pre_state, block, traces_dir)

            current_epoch =  block.header.timeslot // EPOCH_TIMESLOTS
            current_phase =  block.header.timeslot % EPOCH_TIMESLOTS

            logging.info(f'📦 Imported block for #{block.header.timeslot} | hash: {format_hash(block.header.hash)} | epoch #{current_epoch} | phase #{current_phase}')
            logging.info(f'🗳️ Tickets in accumulator: {len(self.state.safrole.ticket_accumulator)}')

        except Exception as e:
            # Rollback state
            logging.error(f'Import failed for #{block.header.timeslot}; Rollback state')
            logging.debug(traceback.format_exc())
            self.state = self.retrieve_jam_state()
            raise e

    return cli_import_block


def wrap_produced_block_jamnp(app: PyjamazApp, traces_dir, np_protocol: JAMNPS):
    async def produced_block_jamnp(block: Block):
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
    app.pubsub = PubSub()
    app.app_context.pubsub = app.pubsub

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
@click.option('--culprit', is_flag=True, help="Culprit mode: node will intentionally act malicious")
@click.option('--block-dir', type=click.Path(exists=True))
@click.option('--record-traces', type=click.Path(exists=True))
@click.option('--db-path', 'custom_db_path', type=click.Path(exists=True))
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--host', 'host', type=str, default="127.0.0.1", show_default=True, help='Host address to listen on')
@click.option('--bootnode', 'bootnode', type=str, default="", show_default=True, help='Specific bootnode to connect to')
async def main(ctx, seed, port, ts, culprit, block_dir, record_traces, custom_db_path, verbose, host, bootnode):
    """PyJAMaz: Python JAM Client"""

    # Note: Add packages that need a different logging level here
    log_package_overrides = {
        "pyjamaz.transport": logging.DEBUG,
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

        logging.info(f'🥋 PyJAMaz JAM client')
        logging.info(f'🧾 Graypaper version: {GP_VERSION} ')
        logging.info(f'💾 Storage path: {db_path}')
        logging.info(f'🌐 Peer ID: {quic_peer_id(app.config.keys.ed25519.public_key)}')
        logging.info(f'🔑 Bandersnatch public: {format_hash(app.config.keys.bandersnatch.public_key)}')
        logging.info(f'🔑 Ed25519 public: {format_hash(app.config.keys.ed25519.public_key)}')
        logging.info(f'🗓️ Common Era: {app.config.common_era} ({datetime.fromtimestamp(app.config.common_era).strftime("%Y-%m-%d %H:%M:%S")})')
        logging.info(f'🌲 State trie root: {format_hash(app.state_trie_root)}')
        logging.info(f'⏱️ Latest timeslot: #{app.state.timeslot.number}')

        logging.info(f'💤 Waiting to start at {datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")}')

        rpc_server = WebSocketServer(app, 'localhost', 19800)

        try:
            async with anyio.create_task_group() as tg:

                # TODO: we need to start this manually in all event loops, make an AppFactory that handles this in a generic way
                # Create a subscriber to process incomming messages (fx from a protocol)
                tg.start_soon(app.pubsub.process_messages)

                # Start WebSocket server
                tg.start_soon(start_rpc_server, rpc_server)

                if block_dir:
                    logging.info(f"👀 Watching directory: {block_dir} for new blocks...")
                    fs_protocol = FSProtocol(block_dir, app)
                    app.protocol = fs_protocol
                    app.pubsub.subscribe(MESSAGE_TYPES.PRODUCED_BLOCK, wrap_produced_block_fs(app, record_traces, fs_protocol))
                    app.pubsub.subscribe(MESSAGE_TYPES.RECEIVED_BLOCK, app.import_block_from_json)
                    app.pubsub.subscribe(MESSAGE_TYPES.REQUESTED_BLOCKS, app.requested_blocks_from_json)
                    tg.start_soon(fs_protocol.listen)
                else:
                    certificate_file = os.path.join(db_path, "cert.pem")
                    pk_file = os.path.join(db_path, "cert.key")
                    nps_protocol = JAMNPS(host, port, certificate_file, pk_file, app)
                    app.protocol = nps_protocol
                    app.pubsub.subscribe(MESSAGE_TYPES.PRODUCED_BLOCK, wrap_produced_block_jamnp(app, record_traces, nps_protocol))
                    app.pubsub.subscribe(MESSAGE_TYPES.RECEIVED_BLOCK, app.import_block_from_bytes)
                    app.pubsub.subscribe(MESSAGE_TYPES.REQUESTED_BLOCKS, app.requested_blocks_from_bytes)
                    tg.start_soon(nps_protocol.listen)

                    for validator in app.state.safrole.validators:
                        # The validators' IP-layer endpoints are given as IPv6/port combinations,
                        # to be found in the first 18 bytes of validator metadata, with the first 16 bytes being the IPv6 address and
                        # the latter 2 being a little endian representation of the port.

                        validator_port = validator.get_metadata_port()
                        validator_address = validator.get_metadata_ipaddress()

                        if validator.ed25519 == app.config.keys.ed25519.public_key:
                            logging.debug(
                                f'Skipping own node ({validator_address}:{validator_port})'
                            )
                            continue

                        logging.debug(f'Connecting to node {validator_address}:{validator_port}')
                        tg.start_soon(nps_protocol.connect, validator_address, validator_port)

                await anyio.sleep(ts - time.time())
                tg.start_soon(timeslot_ticker, app)
        except (KeyboardInterrupt, CancelledError):
            logging.info("Stopping node...")
            # stop_event.set()
        finally:
            logging.info(f'Node stopped.')


async def timeslot_ticker(app: PyjamazApp):

    while True:
        # TODO centralize
        app.block_context.reset()
        timeslot = app.current_timeslot()

        epoch = timeslot // EPOCH_TIMESLOTS
        phase = timeslot % EPOCH_TIMESLOTS

        logging.debug(f"⏳️ Timeslot ticker: {timeslot}")

        if app.state.timeslot.number >= timeslot:
            logging.debug('⚠️ Timeslot did not advance; yield for 0.1 seconds')
            await anyio.sleep(0.1)
            continue

        if app.is_epoch_change(timeslot):
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

        if app.should_produce_block(timeslot, safrole_state):

            try:
                await app.process_assurances()

                block = await app.produce_block(timeslot, safrole_state, entropy_state)

                await app.pubsub.publish(PubSubSignal(topic=MESSAGE_TYPES.PRODUCED_BLOCK, data=block))

                logging.info(f'🎁 Produced block for #{block.header.timeslot} | hash: {format_hash(block.header.hash)} | epoch #{epoch} | phase #{phase}')
            except Exception as e:
                logging.info(f'🗑️ Discarded produced block for #{timeslot}: {e}')
                # Rollback state from DB
                app.state = app.retrieve_jam_state()
                # TODO Make transactional
                app.extrinsic.clear_tickets()
                raise e

        else:
            logging.info(f'💤 Waiting for block #{timeslot} | epoch #{epoch} | phase #{phase}')

        if app.get_core_assigment() is not None:

            # TODO TBD when does refine etc start
            work_report = await app.process_refine(timeslot)

            if work_report:
                logging.info(f'👨‍💻 Refine complete | slot={timeslot} | core={app.get_core_assigment()} | work_report={format_hash(work_report.package_spec.hash)}')


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
        ips="127.0.0.1",    #TODO: hardcoded for now
        alternative_name="e3r2oc62zwfj3crnuifuvsxvbtlzetk4o5qyhetkhagsc2fgl2oka",
    )
    pk_file = os.path.join(db_path, "cert.key")
    pem_file = os.path.join(db_path, "cert.pem")
    write_cert(pk_pem, pk_file, cert_pem, pem_file)


@main.command()
@click.option('--seed', 'seed', type=str, help="Seed to use for validator keys")
@click.option('--chainspec', 'chainspec', type=click.Choice(['dev', 'docker']), help="Chainspec to use as genesis", default='dev')
@click.option('--db-path', 'custom_db_path', type=click.Path())
@click.option('--force-overwrite', is_flag=True, help="Skip confirmation to overwrite existing database")
async def init(
        custom_db_path,
        force_overwrite,
        seed,
        chainspec
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

    if os.path.isdir(db_path):
        if not force_overwrite:
            click.confirm(f"Database already exists at '{db_path}', delete?", abort=True)
        shutil.rmtree(db_path)  # Delete the directory if it exists
        click.echo(f"The database at '{db_path}' was deleted successfully.")

    app = await initialize_app(read_state=False, custom_db_path=custom_db_path)

    # Load chainspec
    with open(os.path.join(data_dir, 'chainspecs', f'{chainspec}-spec.json'), 'r') as fp:
        chainspec_data = json.load(fp)

    # Store state data
    for k, v in chainspec_data["genesis_state"].items():
        app.state_db.put(bytes.fromhex(k), bytes.fromhex(v))

    # Create genesis block
    genesis_block = Block(
        header=Header.from_jam_bytes(JamBytes(bytes.fromhex(chainspec_data["genesis_header"]))),
        extrinsic=Extrinsic.default()
    )

    # Store genesis block
    await app.store_block(genesis_block)

    click.echo(f'📦 Genesis block successfully saved (hash: {format_hash(genesis_block.header.hash)})')

    # Initialize certificate
    await init_certificate(db_path, seed)

    logging.debug("Updating state trie..")
    await app.update_state_trie()

    click.echo(f"✅ Initialization complete.")
    click.echo(f'🌲 State trie root: {format_hash(app.state_trie_root)}')


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
@click.option('--chainspec', 'chainspec', type=str, help="Chainspec to use as genesis (e.g. testnet-tiny")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
async def replay_traces(
        traces_dir, custom_db_path, force_overwrite, skip_block_validation,
        only_block_import, trace_format, seed, chainspec, verbose
):
    # Safety checks
    if SOLO_MODE is True:
        raise BadParameter("settings.SOLO_MODE cannot be True when running traces")

    log_level = logging.DEBUG if verbose else logging.INFO
    setup_logging(log_level)

    db_path = custom_db_path or default_db_path

    if seed is None:
        raise MissingParameter("--seed parameter is required")
    elif not seed.startswith("0x") or len(seed) != 66:
        raise BadParameter("Seed should start with '0x' and have a length of 66 chars")

    if only_block_import:
        app = await initialize_app(read_state=True, custom_db_path=custom_db_path)
    else:
        # Flush database and import genesis state
        if os.path.isdir(db_path):
            if not force_overwrite:
                click.confirm(f"Database already exists at '{db_path}', delete?", abort=True)
            shutil.rmtree(db_path)  # Delete the directory if it exists
            logging.info(f"The database at '{db_path}' was deleted successfully.")

        os.makedirs(db_path, exist_ok=True)
        if not os.path.isfile(os.path.join(db_path, "cert.key")) or force_overwrite:
            await init_certificate(db_path, seed)

        app = await initialize_app(read_state=False, custom_db_path=custom_db_path)

        if chainspec:
            with open(os.path.join(data_dir, 'chainspecs', f'{chainspec}-db.bin'), 'rb') as fp:
                genesis_state = StateDump.from_jam_bytes(JamBytes(fp.read()))
                for k, v, name, metadata in genesis_state.keyvals:
                    app.state_db.put(bytes(k), bytes(v))

                app.state = app.retrieve_jam_state()
                await app.update_state_trie()

                assert app.state_trie_root == genesis_state.state_root
                logging.info(f'🎬 Genesis successfully saved (state root: {format_hash(app.state_trie_root)})')

            with open(os.path.join(data_dir, 'chainspecs', f'{chainspec}-block.bin'), 'rb') as fp:
                genesis_block = Block.from_jam_bytes(JamBytes(fp.read()))

                app.block_context.ancestor_headers.append(genesis_block.header)

                logging.info(f'📦 Genesis block successfully saved (hash: {format_hash(genesis_block.header.hash)})')

    traces_files = await anyio.to_thread.run_sync(
        lambda: sorted({f for f in os.listdir(traces_dir) if f.endswith('.bin')})
    )

    for nr, block_file in enumerate(traces_files, start=1):
        logging.info(f'📂 Processing trace file {block_file}')

        with open(os.path.join(traces_dir, block_file), 'rb') as fp:
            trace = Trace.from_jam_bytes(JamBytes(fp.read()))

        if trace.pre_state.state_root == bytes(32):
            # Skip genesis creation
            continue

        if not only_block_import:

            # Update state from trace pre-state
            for k, v in trace.pre_state.keyvals:
                app.state_db.put(bytes(k), bytes(v))

            app.state = app.retrieve_jam_state()
            await app.update_state_trie()

            if app.state_trie_root == trace.pre_state.state_root:
                logging.info(f'🎬 Pre-state successfully saved (state root: {format_hash(app.state_trie_root)})')
            else:
                logging.error("State root of pre-state doesn't match")

            # Add stub parent as ancestor
            stub_parent = Header.default()
            stub_parent.hash = trace.block.header.parent
            stub_parent.timeslot = trace.block.header.timeslot - 1
            app.block_context.ancestor_headers.append(stub_parent)

        logging.info(f'⚙️ Processing block {trace.block.header.timeslot} (hash: {format_hash(trace.block.header.hash)})')

        await app.import_block(trace.block, dry_run=skip_block_validation)
        # Update Patricia Trie
        await app.update_state_trie()

        logging.info(f'✅ Block {trace.block.header.timeslot} successfully imported.')

        if not only_block_import:

            if app.state_trie_root == trace.post_state.state_root:
                logging.info(f'✅ State trie root matches ({format_hash(trace.post_state.state_root)})')
            else:
                logging.error(f'State root of trace {format_hash(trace.post_state.state_root)} does not match with current state {format_hash(app.state_trie_root)}')

                # Diffing DBs
                db_dump = {k.hex(): v.hex() for k, v in list(app.state_db)}
                trace_db = [(k.hex(),v.hex()) for k, v in trace.post_state.keyvals]

                for k, v in trace_db:
                    if k not in db_dump:
                        logging.warning(f'key {k} is missing')
                    elif v != db_dump[k]:
                        logging.warning(f'key {k} is different: {db_dump[k]} != {v}')

                tracedb_keys = {k for k, v in trace_db}

                for k, v in db_dump.items():
                    if k not in tracedb_keys:
                        logging.warning(f'key {k} is not present in trace: {v}')

                state_dump_file = f'state_{block_file.replace(".bin", "")}.json'

                with open(os.path.join(traces_dir, state_dump_file), 'w') as file:
                    json.dump(app.state.to_json(), file, indent=2)
                logging.info(f"Current state written to disk: {state_dump_file}")

                # Update state from trace post-state
                for k, v in trace.post_state.keyvals:
                    app.state_db.put(bytes(k), bytes(v))

                app.state = app.retrieve_jam_state()
                await app.update_state_trie()

                state_dump_file = f'trace_post_{block_file.replace(".bin", "")}.json'

                with open(os.path.join(traces_dir, state_dump_file), 'w') as file:
                    json.dump(app.state.to_json(), file, indent=2)
                logging.info(f"Trace post-state written to disk: {state_dump_file}")

                if nr < len(traces_files):
                    response = click.prompt("Press Enter to continue or type 'q' to quit", default='', show_default=False)
                    if response.lower() == 'q':
                        logging.info('✋ User aborted.')
                        break

            # Flush DB
            for key, _ in app.state_db:
                app.state_db.delete(key)


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


@main.command('set_bootstrap')
@click.argument('bootstrap_service', type=click.Path(exists=True))
@click.option('--chainspec', 'chainspec', type=str, help="Chainspec to use as genesis (e.g. testnet-tiny")
async def set_bootstrap(
        bootstrap_service, chainspec
):
    # log_level = logging.INFO
    # setup_logging(log_level)

    # with open(os.path.join(data_dir, 'chainspecs', f'testnet-tiny-db.bin'), 'rb') as fp:
    #     genesis_state = ChainspecDump.from_jam_bytes(JamBytes(fp.read()))
    #
    # del genesis_state.keyvals[1]
    # del genesis_state.keyvals[2]
    # del genesis_state.keyvals[17]
    #
    #
    # with open(os.path.join(data_dir, 'chainspecs', f'skeleton-tiny-db.bin'), 'wb') as fp:
    #     fp.write(genesis_state.to_jam_bytes().to_bytes())
    #
    # exit()

    with open(os.path.join(data_dir, 'chainspecs', f'skeleton-tiny-db.bin'), 'rb') as fp:
        genesis_state = ChainspecDump.from_jam_bytes(JamBytes(fp.read()))

    with open(bootstrap_service, 'rb') as fp:
        bootstrap_blob = fp.read()

    bootstrap_hash = blake2b_256_hash(bootstrap_blob)

    service_account_id = 0

    # Service account
    state_key = state_key_constructor_service_account(service_account_id)
    service_account = ServiceAccount(
        code_hash=bootstrap_hash,
        balance=10000000000,
        gas_limit_accumulate=100,
        gas_limit_on_transfer=100,
        footprint_storage_items=0,
        footprint_storage_bytes=0,
        storage_items={},
        preimages={},
        preimage_availability={}
    )

    service_account.update_footprint_add_preimage(len(bootstrap_blob))

    genesis_state.keyvals.append((state_key, service_account.to_serialized_bytes()))

    # Preimage
    genesis_state.keyvals.append(
        (state_key_constructor_preimage(service_account_id, bootstrap_hash), bootstrap_blob)
    )

    # Preimage availability
    genesis_state.keyvals.append(
        (state_key_constructor_preimage_availability(service_account_id, bootstrap_hash, len(bootstrap_blob)),
         bytes.fromhex('0100000000'))
    )

    genesis_state.keyvals = sorted(genesis_state.keyvals, key=lambda x: x[0])

    output = genesis_state.to_json()

    with open(os.path.join(data_dir, 'chainspecs', f'{chainspec}-db.bin'), 'wb') as fp:
        fp.write(genesis_state.to_jam_bytes().to_bytes())


if __name__ == '__main__':
    main(_anyio_backend="asyncio")
