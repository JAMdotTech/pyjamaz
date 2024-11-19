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
from pyjamaz.models.stf_output import STFOutput
from pyjamaz.storage import LevelDBStorage, InMemoryStorage
from pyjamaz.models.block import Block, Header
from pyjamaz.models.state import JamState

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
async def main(ctx, seed, port, ts, mode, culprit, block_dir, traces_dir, custom_db_path, verbose):
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
        try:
            async with anyio.create_task_group() as tg:
                if block_dir:
                    tg.start_soon(timeslot_ticker, app, block_dir, traces_dir, lock)
                    logger.info(f"👀 Watching directory: {block_dir} for new blocks...")
                    tg.start_soon(local_block_importer, app, block_dir, traces_dir, lock)
                else:
                    logger.error("Networking not implemented yet; use --block-dir for filesystem mode")
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
                            if block.header.timeslot > app.state.timeslot.number or (app.state.timeslot.number == 0 and not app.should_produce_block()):

                                if traces_dir:
                                    pre_state = app.state.to_json()

                                output = await app.import_block(block)

                                if traces_dir:
                                    await store_trace(pre_state, block, output, app, traces_dir)

                                logger.info(f"📦 Imported: {os.path.basename(filepath)}")
                                logger.info(f'🗳️ Tickets in accumulator: {len(app.state.safrole.ticket_accumulator)}')
                            else:
                                logger.info(f"⏭️ Skipped: {os.path.basename(filepath)}")

                except Exception as e:
                    logger.error(f"Failed to process {filepath}: {e}")

            # Update the seen_files set to include the newly processed files
            seen_files.update(new_files)

        await anyio.sleep(.5)


async def timeslot_ticker(app: PyjamazApp, block_dir, traces_dir, lock):

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

                    # write block to dir
                    filepath = os.path.join(block_dir, f'block-{block.header.timeslot:06}.json')
                    with open(filepath, 'w') as file:
                        json.dump(block.to_json(), file, indent=2)

                    logger.info(f'🎁 Produced block for #{block.header.timeslot} | hash: 0x{block.header.hash.hex()}')
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
@click.option('--genesis', type=click.Path())
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

    app = initialize_app(read_state=False, custom_db_path=custom_db_path, common_era=common_era)
    app.store_jam_state(jam_state)
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
