import logging
from asyncio import CancelledError
from datetime import datetime
import json
import os
import shutil

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
from pyjamaz.models.common import ValidatorData
from pyjamaz.models.trace import Trace
from pyjamaz.storage import LevelDBStorage, InMemoryStorage, TransactionRolledBack
from pyjamaz.models.block import Block, Header
from pyjamaz.models.state import JamState
from pyjamaz.utils import format_hash

data_dir = path.join(path.dirname(path.abspath(__file__)), 'data')
default_db_path = path.join(data_dir, 'db')

logger = logging.getLogger(__name__)


async def initialize_app(read_state=True, memory_storage=False, keys=None, common_era=None, custom_db_path=None) -> PyjamazApp:

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
        await app.update_state_trie()

    return app


# CLI commands

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
@click.option('--record-traces', type=click.Path(exists=True))
@click.option('--db-path', 'custom_db_path', type=click.Path(exists=True))
@click.option('--verbose', is_flag=True, help="Enable verbose output")
async def main(ctx, seed, port, ts, mode, culprit, block_dir, record_traces, custom_db_path, verbose):
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
            app = await initialize_app(
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
        logger.info(f'🌲 State trie root: 0x{app.state_trie_root.hex()}')
        logger.info(f'⏱️ Latest timeslot: #{app.state.timeslot.number}')

        logger.info(
            f'💤 Waiting to start at {datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")}'
            )
        await anyio.sleep(ts - time.time())

        lock = anyio.Lock()
        try:
            async with anyio.create_task_group() as tg:
                if block_dir:
                    tg.start_soon(timeslot_ticker, app, block_dir, lock)
                    logger.info(f"👀 Watching directory: {block_dir} for new blocks...")
                    tg.start_soon(local_block_importer, app, block_dir, record_traces, lock)
                else:
                    logger.error("Networking not implemented yet; use --block-dir for filesystem mode")
        except (KeyboardInterrupt, CancelledError):
            logger.info("Stopping node...")
        finally:
            logger.info(f'Node stopped.')


async def local_block_importer(app: PyjamazApp, block_dir, traces_dir, lock):

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
                            if block.header.timeslot > app.state.timeslot.number:

                                if traces_dir:
                                    pre_state = await app.create_state_dump()

                                await app.import_block(block)

                                app.latest_epoch = block.header.timeslot // EPOCH_TIMESLOTS

                                if traces_dir:
                                    await app.store_trace(pre_state, block, traces_dir)

                                logger.info(f"📦 Imported: {os.path.basename(filepath)}")
                                logger.info(f'🗳️ Tickets in accumulator: {len(app.state.safrole.ticket_accumulator)}')
                            else:
                                logger.info(f"⏭️ Skipped: {os.path.basename(filepath)}")

                except Exception as e:
                    logger.error(f"Failed to process {filepath}: {e}")

            # Update the seen_files set to include the newly processed files
            seen_files.update(new_files)

        await anyio.sleep(.5)


async def timeslot_ticker(app: PyjamazApp, block_dir, lock):

    while True:
        # TODO centralize
        app.block_context.reset()
        timeslot = app.current_timeslot()
        logging.info(f"⏳️Timeslot: {timeslot}")

        if app.state.timeslot.number >= timeslot:
            logger.debug('⚠️ Timeslot did not advance; yield for 0.1 seconds')
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
            # Update slot_sealer_series in advance
            # self.state.safrole.slot_sealer_series = post_safrole_state.post_state.slot_sealer_series
            # logging.debug(f'New slot_sealer_series: {self.state.safrole.slot_sealer_series.to_json()}')
            # Process tickets
            app.extrinsic.process_epoch_change()
            logging.debug(f"Current tickets {[i.hex() for i in app.extrinsic.own_tickets_current]}")

            safrole_state = safrole_output.post_state
            entropy_state = entropy_output.post_state
        else:
            safrole_state = app.state.safrole
            entropy_state = app.state.entropy

        if app.should_produce_block(safrole_state):

            async with lock:
                try:

                    block = await app.produce_block(timeslot, safrole_state, entropy_state)

                    # write block to dir
                    filepath = os.path.join(block_dir, f'block-{block.header.timeslot:06}.json')
                    with open(filepath, 'w') as file:
                        json.dump(block.to_json(), file, indent=2)

                    logger.info(f'🎁 Produced block for #{block.header.timeslot} | hash: 0x{format_hash(block.header.hash)} | epoch #{app.current_epoch()} | phase #{app.current_slot_phase_index()}')
                except Exception as e:
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
@click.option('--genesis', type=click.Path(exists=True))
@click.option('--db-path', 'custom_db_path', type=click.Path())
@click.option('--force-overwrite', is_flag=True, help="Skip confirmation to overwrite existing database")
async def init(initial_state, genesis, custom_db_path, force_overwrite):
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

    app = await initialize_app(read_state=False, custom_db_path=custom_db_path, common_era=common_era)
    await app.store_jam_state(jam_state)
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
async def replay_traces(
        traces_dir, custom_db_path, force_overwrite, skip_block_validation, only_block_import, trace_format
):
    setup_logging(log_level=logging.DEBUG)

    # Flush database and import genesis state
    db_path = custom_db_path or default_db_path
    if os.path.isdir(db_path):
        if not force_overwrite:
            click.confirm(f"Database already exists at '{db_path}', delete?", abort=True)
        shutil.rmtree(db_path)  # Delete the directory if it exists
        logger.info(f"The database at '{db_path}' was deleted successfully.")
    else:
        os.makedirs(db_path, exist_ok=True)

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
            logger.info(f'🎬 Genesis succesfully saved (state root: 0x{app.state_trie_root.hex()})')

        logger.info(f'⚙️ Processing block {trace.block.header.timeslot} (hash: 0x{trace.block.header.hash.hex()})..')
        try:
            await app.import_block(trace.block, validate=not skip_block_validation)
            logger.info(f'✅ Block {trace.block.header.timeslot} succesfully imported.')

        except TransactionRolledBack as e:
            logger.error(f'Failed to import block {trace.block.header.timeslot}: {e}')
            break

        if not only_block_import:

            if app.state_trie_root == trace.post_state.state_root:
                logger.info(f'✅ State trie root matches (0x{trace.post_state.state_root.hex()})')
            else:
                logger.error(f'State root of trace {trace.post_state.state_root.hex()} does not match with current state {app.state_trie_root.hex()}')
                logger.info('Dumping state differences:')
                actual_state = app.state.to_json()

                for k, v, name, metadata in trace.post_state.keyvals:
                    app.state_db.put(bytes(k), bytes(v))

                app.state = app.retrieve_jam_state()

                state_diff = DeepDiff(app.state.to_json(), actual_state, ignore_order=True)
                if state_diff:
                    click.echo(json.dumps(state_diff, indent=2))
                    response = click.prompt("Press Enter to continue or type 'q' to quit", default='', show_default=False)
                    if response.lower() == 'q':
                        logger.info('✋ User aborted.')
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
