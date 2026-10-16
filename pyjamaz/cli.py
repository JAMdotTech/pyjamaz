import bisect
import logging
import traceback
from asyncio import CancelledError
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
import json
import os
import shutil
from pathlib import Path, PosixPath
from typing import List, Tuple, Optional

import anyio
import ipaddress
import time
from os import path

import asyncclick as click
from asyncclick import BadParameter, MissingParameter

from jamcodec.base import JamBytes

from pyjamaz.app import PyjamazApp, AppConfig, Keys
from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.exceptions import StateKeyNoResult, StateTransitionError, BlockValidationError

from pyjamaz.graypaper_constants import COMMON_ERA, EPOCH_TIMESLOTS
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.logger import setup_logging
from pyjamaz.models.app import Trace, TraceGenesis
from pyjamaz.models.state import STORAGE_KEY_MAPPING, ServiceAccount
from pyjamaz.rpc.ws_server import start_rpc_server, WebSocketServer
from pyjamaz.runtime.node_runtime import NodeRuntime
from pyjamaz.settings import GP_VERSION, APP_VERSION, STORAGE_ENGINE, DEBUG
from pyjamaz.storage import InMemoryStorageEngine, RocksDBStorageEngine
from pyjamaz.models.block import Block, Header, Extrinsic
from pyjamaz.fuzzer import FuzzerMessage, InitializeMessage, FuzzerTarget, FuzzerSession, AncestryItem
from pyjamaz.transport.cert import generate_cert, write_cert
from pyjamaz.transport.protocol_fs import FSProtocol
from pyjamaz.transport.protocol_jamnp_s import JAMNPS

from pyjamaz.transport.pubsub import PubSub, PubSubSignal
from pyjamaz.utils import format_hash, quic_peer_id


from pyjamaz.pvm import *


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


def import_block_cli(traces_dir):
    async def cli_import_block(self, block: Block, dry_run=False):

        if traces_dir:
            pre_state = await self.create_state_dump()

        try:
            # Finalize parent
            await self.finalize(block.header.parent)

            await self._import_block(block, dry_run=dry_run)

            if traces_dir:
                await self.store_trace(pre_state, block, traces_dir)

            current_epoch =  block.header.timeslot // EPOCH_TIMESLOTS
            current_phase =  block.header.timeslot % EPOCH_TIMESLOTS

            logging.info(f'📦 Imported block for #{block.header.timeslot} | hash: {format_hash(block.header.hash)} | parent {format_hash(block.header.parent)} | epoch #{current_epoch} | phase #{current_phase}')
            logging.info(f'🗳️ Tickets in accumulator: {len(self.working_state.safrole.ticket_accumulator)}')

        except Exception as e:
            # Rollback state
            logging.error(f'Import failed for #{block.header.timeslot} -> {e}; Rollback state')
            DEBUG and logging.debug(traceback.format_exc())
            self.state_storage.rollback()
            self.working_state = self.retrieve_jam_state()

    return cli_import_block


def import_block_fuzzer(traces_dir):
    async def cli_import_block(self, block: Block, dry_run=False):

        if traces_dir:
            pre_state = await self.create_state_dump()

        await self._import_block(block, dry_run=dry_run)

        if traces_dir:
            await self.store_trace(pre_state, block, traces_dir)

        current_epoch =  block.header.timeslot // EPOCH_TIMESLOTS
        current_phase =  block.header.timeslot % EPOCH_TIMESLOTS

        logging.info(f'📦 Imported block for #{block.header.timeslot} | hash {format_hash(block.header.hash)} | parent {format_hash(block.header.parent)} | epoch #{current_epoch} | phase #{current_phase}')
        logging.info(f'🗳️ Tickets in accumulator: {len(self.working_state.safrole.ticket_accumulator)}')

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
        storage_engine='memory',
        keys=None,
        common_era=None,
        custom_db_path=None,
        record_traces=None,
        pubsub=True,
        block_importer=None,
        d3l_path=None
) -> PyjamazApp:

    # Load SRS
    with open(path.join(data_dir, 'zcash-srs-2-11-uncompressed.bin'), 'rb') as fp:
        ring_data = fp.read()

    # Initiate storage engine
    try:
        DEBUG and logging.debug(f'Selected storage engine: {storage_engine}')

        if storage_engine == 'memory':
            storage_engine = InMemoryStorageEngine()

        elif storage_engine == 'rocksdb':
            storage_engine = RocksDBStorageEngine.create_from_file(custom_db_path or default_db_path)
        else:
            raise ValueError(f'Unsupported storage engine: {storage_engine}')

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
        create_traces=record_traces,
        d3l_path=d3l_path
    )

    if block_importer:
        app = PyjamazApp(config=config, import_block_callback=block_importer(record_traces))
    else:
        app = PyjamazApp(config=config)

    if pubsub:
        app.pubsub = PubSub()
        app.app_context.pubsub = app.pubsub

    if read_state:
        # Retrieve finalized header
        finalized_head_hash = app.retrieve_finalized_head()
        finalized_header = app.retrieve_block_header(finalized_head_hash)
        app.state_storage.set_finalized_header(finalized_header)
        await app.initialize()

    return app


# CLI commands
@click.group()
@click.version_option(version=APP_VERSION)
async def main():
    pass


@main.command(name='run', help='Run a Pyjamaz JAM node')
@click.option('--seed', type=str,
              help='Seed to generate validator keys')
@click.option('--port', type=int, default=9000, show_default=True, help='UDP port on which the validator should run')
@click.option('--ts', type=int, help='Unix timestamp for when the validator starts.')
@click.option('--culprit', is_flag=True, help="Culprit mode: node will intentionally act malicious")
@click.option('--block-dir', type=click.Path(exists=True))
@click.option('--record-traces', type=click.Path(exists=True))
@click.option('--db-path', 'custom_db_path', type=click.Path(), default=default_db_path, show_default=True)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--host', 'host', type=str, default="127.0.0.1", show_default=True, help='Host address to listen on')
@click.option('--bootnode', 'bootnode', type=str, default="", show_default=True, help='Specific bootnode to connect to')
@click.option('--rpc-listen-ip', 'rpc_listen_ip', type=str, default="0.0.0.0", show_default=True, help='IP address for RPC server to listen on')
@click.option('--rpc-port', 'rpc_port', type=int, default=19800, show_default=True, help='Port for RPC server to listen on')
@click.option('--fuzzer', 'fuzzer', is_flag=True, help="Validate trace with fuzzer target")
@click.option('--fuzzer-socket-path', 'fuzzer_socket_path', type=str, default="/tmp/jam_target.sock", show_default=True)
@click.option('--d3l-path', 'd3l_path', type=click.Path())
@click.option('--replay-blocks', 'replay_blocks', type=click.Path())
async def run(seed, port, ts, culprit, block_dir, record_traces, custom_db_path, verbose, host, bootnode, rpc_listen_ip, rpc_port, fuzzer, fuzzer_socket_path, d3l_path, replay_blocks):
    """PyJAMaz: Python JAM Client"""

    # Setup logging
    log_level = logging.DEBUG if verbose or DEBUG else logging.INFO
    # Note: Add packages that need a different logging level here
    log_package_overrides = {
        "pyjamaz.transport": log_level,
        "quic": logging.WARNING,
        "numba": logging.WARNING,
        "numba.core": logging.WARNING
    }
    setup_logging(log_level, log_package_overrides)

    # Safety checks
    if settings.SOLO_MODE:
        logging.warning('settings.SOLO_MODE is enabled')

    if seed is None:
        raise MissingParameter(message="--seed parameter is required to run a node", param_type='option', param_hint='--seed')
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
            record_traces=record_traces,
            storage_engine=STORAGE_ENGINE,
            block_importer=import_block_cli,
            d3l_path=d3l_path
        )
    except StateKeyNoResult:
        raise BadParameter(f'DB is not yet initialized; run init first')

    DEBUG and logging.debug("Retrieving ancestor headers from DB..")

    for header in app.retrieve_ancestor_headers(app.state_storage.finalized_block_hash):
        app.state_storage.add_ancestor(header)

    app.network_bootstrap = network_bootstrap
    common_era_time = datetime.fromtimestamp(app.config.common_era, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if replay_blocks:
        app.config.replay_blocks = TimeslotSelector(replay_blocks)

    if block_dir:
        app.config.import_block_path = block_dir

    logging.info(f'🥋 PyJAMaz JAM client v{APP_VERSION}')
    logging.info(f'🧾 Graypaper version: {GP_VERSION} ')
    logging.info(f'💾 Storage path: {db_path}')
    if d3l_path:
        logging.info(f"💿 D3L path set to {d3l_path}")
    logging.info(f'🌐 Peer ID: {quic_peer_id(app.config.keys.ed25519.public_key)}')
    logging.info(f'🔑 Bandersnatch public: {format_hash(app.config.keys.bandersnatch.public_key)}')
    logging.info(f'🔑 Ed25519 public: {format_hash(app.config.keys.ed25519.public_key)}')
    logging.info(f'🗓️ Common Era: {app.config.common_era} ({common_era_time})')
    logging.info(f'🌲 State trie root: {format_hash(app.working_state.state_root)}')
    logging.info(f'📦 Finalized block: {format_hash(app.state_storage.finalized_block_hash)}')
    logging.info(f'⏱️ Finalized timeslot: #{app.working_state.timeslot.number}')

    logging.info(f'💤 Waiting to start at {datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")}')

    # Start RPC start
    rpc_server = WebSocketServer(app, rpc_listen_ip, rpc_port)

    if fuzzer:
        # Set-up fuzzer
        await setup_fuzzer_session(app, fuzzer_socket_path)

    try:
        async with anyio.create_task_group() as tg:

            # TODO: we need to start this manually in all event loops, make an AppFactory that handles this in a generic way
            # Create a subscriber to process incoming messages (fx from a protocol)
            tg.start_soon(app.pubsub.process_messages)

            # Start WebSocket server
            tg.start_soon(start_rpc_server, rpc_server)

            if False and block_dir:
                # TODO remove
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

                for validator in app.working_state.safrole.validators:
                    # The validators' IP-layer endpoints are given as IPv6/port combinations,
                    # to be found in the first 18 bytes of validator metadata, with the first 16 bytes being the IPv6 address and
                    # the latter 2 being a little endian representation of the port.

                    validator_port = validator.get_metadata_port()
                    validator_address = validator.get_metadata_ipaddress()

                    if validator.ed25519 == app.config.keys.ed25519.public_key:
                        DEBUG and logging.debug(
                            f'Skipping own node ({validator_address}:{validator_port})'
                        )
                        continue

                    DEBUG and logging.debug(f'Connecting to node {validator_address}:{validator_port}')
                    tg.start_soon(nps_protocol.connect, validator_address, validator_port)

            await anyio.sleep(ts - time.time())

            # Create and start runtime
            app.runtime = NodeRuntime(app)
            app.runtime.start(tg)

    except (KeyboardInterrupt, CancelledError):
        logging.info("Stopping node...")
        # stop_event.set()
    finally:
        logging.info(f'Node stopped.')


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
@click.option('--chainspec', 'chainspec', type=click.Choice(['dev', 'docker']), help="Chainspec to use as genesis", default='dev', show_default=True)
@click.option('--db-path', 'custom_db_path', type=click.Path(), default=default_db_path, show_default=True)
@click.option('--import-trace', 'import_trace', type=click.Path())
@click.option('--force-overwrite', is_flag=True, help="Skip confirmation to overwrite existing database")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
async def init(
        custom_db_path,
        force_overwrite,
        seed,
        chainspec,
        verbose,
        import_trace
):
    """
    Clears all existing data and initializes the JAM client.

    Defaults to DEV initial state if none is provided.
    """

    log_level = logging.DEBUG if verbose else logging.INFO
    setup_logging(log_level)

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

    app = await initialize_app(
        read_state=False,
        custom_db_path=custom_db_path,
        storage_engine=STORAGE_ENGINE,
        block_importer=import_block_cli
    )

    if import_trace:

        trace = Trace.from_jam_bytes(JamBytes(Path(import_trace).read_bytes()))

        # Update state from trace post-state
        for k, v in trace.post_state.keyvals:
            app.state_db.put(bytes(k), bytes(v))

        # Add stub parent as ancestor
        stub_parent = Header.default()
        stub_parent.hash = trace.block.header.parent
        stub_parent.timeslot = max(0, trace.block.header.timeslot - 1)
        await app.store_block_header(stub_parent)
        await app.add_ancestor_header(stub_parent)

        # Store block
        await app.store_block(trace.block)
        await app.add_ancestor_header(trace.block.header)
        # Store finalized head
        await app.store_finalized_head(trace.block.header.hash)
        # Set finalized head in state storage
        app.state_storage.set_finalized_header(trace.block.header)

        click.echo(f'📦 State successfully import from trace file {import_trace}')

        logging.debug("Initializating app..")
        await app.initialize(trace.block.header)

    else:
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
        # Store finalized head
        await app.store_finalized_head(genesis_block.header.hash)
        # Set finalized head in state storage
        app.state_storage.set_finalized_header(genesis_block.header)

        click.echo(f'📦 Genesis block successfully saved (hash: {format_hash(genesis_block.header.hash)})')

        logging.debug("Initializating app..")
        await app.initialize(genesis_block.header)

    # Initialize certificate
    await init_certificate(db_path, seed)



    click.echo(f"✅ Initialization complete.")
    click.echo(f'🌲 State trie root: {format_hash(app.working_state.state_root)}')

@main.group('fuzzer', help="Start a fuzzer target or run traces on a fuzzer target")
async def fuzzer():
    pass


def _trace_header_field_key(value):
    """Snapshot codec values with exact types, including mutable containers."""
    value_type = type(value)
    if value is None or value_type in (bytes, int, str, bool, float):
        return value_type, value
    if value_type is bytearray:
        return value_type, bytes(value)
    if value_type in (list, tuple):
        return value_type, tuple(_trace_header_field_key(item) for item in value)
    if is_dataclass(value) and not isinstance(value, type):
        return value_type, tuple(
            _trace_header_field_key(getattr(value, field.name)) for field in fields(value)
        )
    # An unfamiliar codec input may be mutable. Do not reuse its encoding.
    return object()


class _TraceHeader(Header):
    """Cache replay header bytes without changing mutable runtime headers.

    Compare all codec fields with a type-sensitive snapshot before reusing bytes.
    This also detects edits inside epoch markers, tickets and offender lists;
    derived fields such as the author's key do not affect the encoding.
    """

    @classmethod
    def from_header(cls, header: Header) -> "_TraceHeader":
        return cls(**{field.name: getattr(header, field.name) for field in fields(Header)})

    @classmethod
    def to_codec_def(cls):
        # Serializable otherwise changes the shared codec's deserialize type
        # to this replay-only subclass.
        return Header.to_codec_def()

    def _encoded_bytes(self) -> bytes:
        values = tuple(
            _trace_header_field_key(getattr(self, field.name)) for field in fields(Header)
        )
        if values != getattr(self, '_cached_fields', None):
            encoded = super().to_jam_bytes().to_bytes()
            self._cached_fields = values
            self._cached_bytes = encoded
            self._cached_hash = blake2b_256_hash(encoded)
        return self._cached_bytes

    def to_jam_bytes(self) -> JamBytes:
        # JamBytes has a mutable decode offset; callers need their own cursor.
        return JamBytes(self._encoded_bytes())

    @property
    def hash(self) -> bytes:
        self._encoded_bytes()
        return self._cached_hash


def _trace_ancestor_headers(block: Block, known_headers: dict[bytes, Header]) -> List[Header]:
    """Resolve input-header ancestry, oldest first (GP-0.8.0-5.3,11.38).

    Use genesis and preceding block headers, not report claims or expected
    post-state roots, to establish lookup-anchor membership and commitments.
    """
    headers = []
    next_hash = bytes(block.header.parent)
    seen = set()
    while next_hash in known_headers:
        if next_hash in seen:
            raise ValueError("cycle in trace header ancestry")
        seen.add(next_hash)
        header = known_headers[next_hash]
        if bytes(header.hash) != next_hash:
            raise ValueError("trace header does not match its indexed hash")
        child_slot = headers[-1].timeslot if headers else block.header.timeslot
        if header.timeslot >= child_slot:
            raise ValueError("trace ancestor timeslots are not strictly increasing")
        headers.append(header)
        next_hash = bytes(header.parent)
    return list(reversed(headers))


@main.command('traces', help='Run trace files in specified folder')
@click.argument('traces_dir', type=click.Path(exists=True))
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--prompt', is_flag=True, help="Prompt on state diff ")
async def replay_traces(
        traces_dir, verbose, prompt,
):

    log_level = logging.DEBUG if verbose or settings.DEBUG else logging.INFO
    setup_logging(log_level)

    # Safety checks
    if settings.SOLO_MODE:
        raise BadParameter("settings.SOLO_MODE should be False when running traces")

    # Set GP relaxation flags
    settings.SKIP_TIMESLOT_WALL_CLOCK_CHECK = True

    app = await initialize_app(
        read_state=False,
        custom_db_path=None,
        storage_engine='memory',
        pubsub=False,
    )

    traces_folder = Path(traces_dir)

    traces_files = await anyio.to_thread.run_sync(
        lambda: sorted({f for f in list(traces_folder.rglob("*.bin")) if f.name not in ['genesis.bin', 'report.bin']}),
    )

    start_time = time.time()
    mismatch_count = 0
    known_headers: dict[bytes, Header] = {}
    trace_parent = None

    # Process files in traces folder
    for nr, block_file in enumerate(traces_files, start=1):
        logging.info(f'📂 Processing trace file {block_file}')

        trace = Trace.from_jam_bytes(JamBytes(block_file.read_bytes()))

        if trace.pre_state.state_root == bytes(32):
            # Skip genesis creation
            continue

        trace.block.header = _TraceHeader.from_header(trace.block.header)

        # Flush DB
        for key, _ in app.state_db.as_list():
            app.state_db.delete(key)

        # Clear pending changesets
        app.state_storage.clear()
        # Each trace supplies an independent pre-state; do not reuse a cached
        # state merely because the next header claims the same parent root.
        app.working_state = None

        if block_file.parent != trace_parent:
            known_headers.clear()
            genesis_file = block_file.parent / "genesis.bin"
            if genesis_file.exists():
                genesis = TraceGenesis.from_jam_bytes(JamBytes(genesis_file.read_bytes()))
                genesis.header = _TraceHeader.from_header(genesis.header)
                known_headers[bytes(genesis.header.hash)] = genesis.header
            trace_parent = block_file.parent
        ancestor_headers = _trace_ancestor_headers(trace.block, known_headers)
        if not ancestor_headers and trace.block.header.timeslot != 0:
            raise click.ClickException(
                f"trace {block_file} is missing its parent header; provide the "
                "corpus genesis.bin and preceding trace inputs"
            )
        known_headers[bytes(trace.block.header.hash)] = trace.block.header
        app.state_storage.set_finalized_block_hash(trace.block.header.parent)

        # Update state from trace pre-state
        for k, v in trace.pre_state.keyvals:
            app.state_db.put(bytes(k), bytes(v))

        for ancestor_header in ancestor_headers:
            await app.store_block_header(ancestor_header)
            await app.add_ancestor_header(ancestor_header)

        # Store block
        await app.store_block(trace.block)
        await app.add_ancestor_header(trace.block.header)

        await app.initialize(header=trace.block.header)

        if app.working_state.state_root == trace.pre_state.state_root:
            logging.info(f'🎬 Pre-state successfully saved (state root: {format_hash(app.working_state.state_root)})')
        else:
            raise click.ClickException(f"Pre-state root mismatch in trace {block_file}")

        logging.info(f'⚙️ Processing block {trace.block.header.timeslot} (hash={format_hash(trace.block.header.hash)} parent={format_hash(trace.block.header.parent)} parent_state_root={format_hash(trace.block.header.parent_state_root)})')

        try:
            # Import block
            await app.import_block(trace.block)

            logging.info(f'✅ Block {format_hash(trace.block.header.hash)} successfully imported.')

        except (StateTransitionError, BlockValidationError) as e:
            logging.info(f"🛑 Block {format_hash(trace.block.header.hash)} raised error -> {e}")
            # The application has already discarded the rejected candidate.

        # Validate new state root
        if app.working_state.state_root == trace.post_state.state_root:
            logging.info(f'✅ State trie root matches ({format_hash(trace.post_state.state_root)})')
        else:
            mismatch_count += 1
            logging.error(f'State root mismatch in trace "{block_file.parent.name}/{block_file.name}": their={format_hash(trace.post_state.state_root)}  ours={format_hash(app.working_state.state_root)}')

            # Diffing DBs
            process_state_diff(app.state_storage.as_list(), trace.post_state.keyvals, block_file)

            if nr < len(traces_files) and prompt:
                response = await click.prompt("Press Enter to continue or type 'q' to quit", default='', show_default=False)
                if response.lower() == 'q':
                    logging.info('✋ User aborted.')
                    break

    logging.info(f'Traces finished in {time.time() - start_time} seconds')
    if mismatch_count:
        raise click.ClickException(
            f"{mismatch_count} trace state-root mismatch{'es' if mismatch_count != 1 else ''}"
        )

@fuzzer.command('traces', help='Start Fuzzer target over UNIX socket.')
@click.argument('traces_dir', type=click.Path(exists=True))
@click.option('--socket-path', 'socket_path', type=str, default="/tmp/jam_target.sock", show_default=True)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--prompt-on-diff', is_flag=True, help="Prompt on state diff ")
async def fuzzer_traces(traces_dir: str, socket_path: str, verbose: bool, prompt_on_diff: bool):
    from pyjamaz.merkle import PatriciaMerkleTrie

    log_level = logging.DEBUG if verbose else logging.INFO
    setup_logging(log_level)

    fuzzer_session = FuzzerSession(socket_path, app=None)
    start_time = time.time()
    connected = False
    mismatch_count = 0
    last_parent = None

    def require_response(response, field, operation):
        if response.error is not None:
            raise click.ClickException(f'Fuzzer {operation} failed: {response.error}')
        value = getattr(response, field)
        if value is None:
            raise click.ClickException(f'Unexpected fuzzer response to {operation}: expected {field}')
        return value

    try:
        await fuzzer_session.connect()
        connected = True
        logging.info('Fuzzer session started.')

        traces_folder = Path(traces_dir)
        traces_files = await anyio.to_thread.run_sync(
            lambda: sorted(f for f in traces_folder.rglob("*.bin") if f.name not in ['genesis.bin', 'report.bin']),
        )

        for block_file in traces_files:
            logging.info(f'📂 Processing trace file {block_file}')
            trace = Trace.from_jam_bytes(JamBytes(block_file.read_bytes()))

            if block_file.parent != last_parent:
                # Initialize
                ancestry = []
                genesis_file = block_file.parent / "genesis.bin"

                if genesis_file.exists():
                    genesis = TraceGenesis.from_jam_bytes(JamBytes(genesis_file.read_bytes()))
                    state = genesis.state
                    init_header = genesis.header

                else:
                    # Unknown genesis; add stub parent as ancestor
                    init_header = Header.default()
                    state = trace.pre_state
                    if trace.block.header.timeslot > 0:
                        ancestry = [
                            AncestryItem(slot=trace.block.header.timeslot - 1, header_hash=trace.block.header.parent)
                        ]

                request = FuzzerMessage(
                    initialize=InitializeMessage(
                        state=state.keyvals,
                        header=init_header,
                        ancestry=ancestry
                    ),
                )
                response = await fuzzer_session.send_request(request)
                state_root = require_response(response, 'state_root', 'Initialize')

                logging.info(f'💾 Fuzzer: Set state: {format_hash(state_root)}')
                if state_root != state.state_root:
                    raise click.ClickException(
                        f'Fuzzer initial state root mismatch: exp={format_hash(state.state_root)} got={format_hash(state_root)}'
                    )

                last_parent = block_file.parent

            verbose and logging.debug(f'Import block: h={format_hash(trace.block.header.hash)} p={format_hash(trace.block.header.parent)} ts={trace.block.header.timeslot}')
            response = await fuzzer_session.send_request(FuzzerMessage(import_block=trace.block))

            if response.error is not None:
                logging.info(f'🛑 Target reported error for {format_hash(trace.block.header.hash)}: {response.error}')
                # A rejected block must leave its parent's state intact. Read
                # that state from the target rather than trusting the fixture.
                response = await fuzzer_session.send_request(FuzzerMessage(get_state=trace.block.header.parent))
                state_root = PatriciaMerkleTrie(require_response(response, 'state', 'GetState')).root()
            else:
                state_root = require_response(response, 'state_root', 'ImportBlock')

            if state_root == trace.post_state.state_root:
                logging.info(f'✅ State root matches for block {format_hash(trace.block.header.hash)} ({format_hash(state_root)})')
            else:
                mismatch_count += 1
                logging.error(f'Fuzzer state root mismatch in trace "{block_file.parent.name}/{block_file.name}": exp={format_hash(trace.post_state.state_root)} got={format_hash(state_root)}')
                if prompt_on_diff:
                    answer = await click.prompt("Press Enter to continue or type 'q' to quit", default='', show_default=False)
                    if answer.lower() == 'q':
                        logging.info('✋ User aborted.')
                        break
    finally:
        # connect() can fail during the handshake after opening the socket.
        if connected or getattr(fuzzer_session, 'writer', None) is not None:
            await fuzzer_session.close()

    logging.info(f'Fuzzer session finished in {time.time() - start_time} seconds')
    if mismatch_count:
        raise click.ClickException(
            f"{mismatch_count} fuzzer trace state-root mismatch{'es' if mismatch_count != 1 else ''}"
        )


@fuzzer.command('target', help='Start Fuzzer target over UNIX socket.')
@click.option('--socket-path', 'socket_path', type=str, default="/tmp/jam_target.sock", show_default=True)
@click.option('--db-path', 'db_path', type=click.Path(), default=None, show_default=True, help="[deprecated]")
@click.option('--force-overwrite', is_flag=True, help="Skip confirmation to overwrite existing database [deprecated]")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
async def fuzzer_target(db_path, force_overwrite, socket_path, verbose):

    log_level = logging.DEBUG if verbose else logging.INFO
    setup_logging(log_level)

    # Safety checks
    if settings.SOLO_MODE:
        logging.warning('settings.SOLO_MODE is enabled')

    # Set GP relaxation flags
    settings.SKIP_TIMESLOT_WALL_CLOCK_CHECK = True

    app = await initialize_app(
        read_state=False,
        storage_engine='memory',
        pubsub=False
    )

    try:
        srv = FuzzerTarget(socket_path, app)
        await srv.start()
    except (KeyboardInterrupt, CancelledError):
        logging.info("Stopping fuzzer...")
    finally:
        logging.info(f'Fuzzer stopped.')


# Helper functions

async def setup_fuzzer_session(app: PyjamazApp, fuzzer_socket_path: str):
    fuzzer_session = FuzzerSession(fuzzer_socket_path, app=app)
    await fuzzer_session.connect()

    logging.info(f'Fuzzer session started.')

    initial_block = app.retrieve_block(app.working_state.timeslot.number)

    request = FuzzerMessage(
        set_state=InitializeMessage(state=list(app.state_db.as_list()), header=initial_block.header),
    )
    response = await fuzzer_session.send_request(request)

    logging.info(f'Fuzzer: Set state: {format_hash(response.state_root)}')

    if response.state_root != app.working_state.state_root:
        logging.error('Fuzzer state root mismatch')
        exit(2)

    async def process_block(block: Block):
        # Replace
        response = await fuzzer_session.send_request(
            FuzzerMessage(
                import_block=block
            )
        )
        if response.state_root == app.working_state.state_root:
            logging.info(f'[Fuzzer] Block successfully imported: state_root={format_hash(app.working_state.state_root)}')
        else:
            logging.error(f'[Fuzzer] Post state-root does not match: {format_hash(response.state_root)}')
            # Retrieve state from target
            response = await fuzzer_session.send_request(
                FuzzerMessage(
                    get_state=block.header.hash
                )
            )
            process_state_diff(app.state_storage.as_list(), response.state)

    # Subscribe to BEST_BLOCK to import them in fuzzer target
    app.pubsub.subscribe(MESSAGE_TYPES.BEST_BLOCK, process_block)


def process_state_diff(my_state: List[Tuple[bytes, bytes]], other_state: List[Tuple[bytes, bytes]], trace_file: PosixPath):
    my_state = {bytes(k): bytes(v) for k, v in my_state}
    other_state = [(bytes(k), bytes(v)) for k, v in other_state]

    for k, v in other_state:
        if k not in my_state:
            logging.warning(f'key {k.hex()} is missing')
            write_storage_key_diff(k, None, v, trace_file)

        elif v != my_state[k]:
            logging.warning(f'key {k.hex()} is different: {my_state[k].hex()} != {v.hex()}')
            write_storage_key_diff(k, my_state[k], v, trace_file)

    tracedb_keys = {k for k, v in other_state}

    for k, v in my_state.items():
        if k not in tracedb_keys:
            logging.warning(f'key {k.hex()} is not present in trace: {v.hex()}')
            write_storage_key_diff(k, v, None, trace_file)


def write_storage_key_diff(storage_key: bytes, mine: Optional[bytes], theirs: Optional[bytes], trace_file: PosixPath):
    # Save (decoded) diffs
    if storage_key[0] == 255 and storage_key[-8:] == bytes(8):
        # ServiceAccount
        service_id = int.from_bytes(storage_key[1:2] + storage_key[3:4] + storage_key[5:6] + storage_key[7:8], byteorder='little')

        if mine is not None:
            mine_file = trace_file.parent / f'{trace_file.name}-service-{service_id}-mine.json'
            my_value = ServiceAccount.from_serialized_bytes(mine)
            mine_file.write_text(json.dumps(my_value.to_json(), indent=2))

        if theirs is not None:
            theirs_file = trace_file.parent / f'{trace_file.name}-service-{service_id}-theirs.json'
            theirs_value = ServiceAccount.from_serialized_bytes(theirs)
            theirs_file.write_text(json.dumps(theirs_value.to_json(), indent=2))

    elif STORAGE_KEY_MAPPING.get(storage_key):
        state_cls = STORAGE_KEY_MAPPING.get(storage_key)

        # StateComponent
        if mine is not None:
            mine_file = trace_file.parent / f'{trace_file.name}-{state_cls.__name__}-mine.json'
            my_value = state_cls.from_jam_bytes(JamBytes(mine))
            mine_file.write_text(json.dumps(my_value.to_json(), indent=2))

        if theirs is not None:
            theirs_file = trace_file.parent / f'{trace_file.name}-{state_cls.__name__}-theirs.json'
            theirs_value = state_cls.from_jam_bytes(JamBytes(theirs))
            theirs_file.write_text(json.dumps(theirs_value.to_json(), indent=2))

    else:
        # Other
        if mine is not None:
            mine_file = trace_file.parent / f'{trace_file.name}-{storage_key[0:4].hex()}-mine.txt'
            mine_file.write_text(mine.hex())
        if theirs is not None:
            theirs_file = trace_file.parent / f'{trace_file.name}-{storage_key[0:4].hex()}-theirs.txt'
            theirs_file.write_text(theirs.hex())


class TimeslotSelector:
    def __init__(self, folder_path):
        folder = Path(folder_path)

        self.timeslots = []
        self.file_map = {}

        for file in folder.glob("*.bin"):
            try:
                ts = int(file.stem)
                self.timeslots.append(ts)
                self.file_map[ts] = file
            except ValueError:
                continue

        self.timeslots.sort()

    def find_next(self, target_timeslot) -> Optional[Block]:
        if not self.timeslots:
            return None

        idx = bisect.bisect_right(self.timeslots, target_timeslot)

        if idx >= len(self.timeslots):
            idx = 0

        ts = self.timeslots.pop(idx)
        file_path = self.file_map.pop(ts)

        with open(file_path, "rb") as f:
            data = f.read()
            trace = Trace.from_jam_bytes(JamBytes(data))
            return trace.block

if __name__ == '__main__':
    main(_anyio_backend="asyncio")
