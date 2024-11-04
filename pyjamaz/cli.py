from asyncio import CancelledError
from datetime import datetime
import json
import os
import shutil

import anyio
import sys

import time
from os import path

import asyncclick as click
from asyncclick import BadParameter
from deepdiff import DeepDiff

from jamcodec.base import JamBytes
from pyjamaz import __version__
from pyjamaz.app import PyjamazApp, AppConfig, Keys
from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.models.stf_output import STFOutput
from pyjamaz.storage import LevelDBStorage, InMemoryStorage
from pyjamaz.models.block import Block
from pyjamaz.models.state import JamState

data_dir = path.join(path.dirname(path.abspath(__file__)), 'data')
default_db_path = path.join(data_dir, 'db')


def error_message(message: str):
    formatted_date_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    click.echo(
        click.style(formatted_date_time, fg=(80, 80, 80)) + '  ' + click.style(f'⚠️ {message}', fg='red'), err=True
    )


def info_message(message: str):
    formatted_date_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    click.echo(click.style(formatted_date_time, fg=(80, 80, 80)) + '  ' + message)


def initialize_app(read_state=True, memory_storage=False, keys=None, epoch=None, custom_db_path=None) -> PyjamazApp:

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
        error_message(f'Could not initialize storage engine: {str(e)}')
        exit(2)

    # Set epoch
    if not epoch:
        epoch = 12

    if epoch < 10000:
        # epoch is relative to current time
        current_time = time.time()
        epoch = int(current_time - (current_time % epoch) + epoch)

    # Initialize app
    config = AppConfig(
        ring_data=ring_data,
        storage_engine=storage_engine,
        keys=keys,
        epoch=epoch
    )

    app = PyjamazApp(config=config)

    if read_state:
        app.state = app.retrieve_jam_state()

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
async def main(ctx, seed, port, ts, mode, culprit, block_dir, traces_dir, custom_db_path):
    """PyJAMaz: Python JAM Client"""

    if ctx.invoked_subcommand is None:

        if mode != 'safrole':
            raise BadParameter(f'{mode} is not supported yet')

        db_path = custom_db_path or default_db_path

        try:
            app = initialize_app(
                keys=Keys.from_seed(bytes.fromhex(seed[2:])),
                epoch=ts,
                custom_db_path=custom_db_path
            )
        except StateKeyNoResult:
            raise BadParameter(f'DB is not yet initialized; run init first')

        info_message(f'🥋 Starting PyJAMaz client, listening on port {port}')
        info_message(f'💾 Storage path: {db_path}')
        info_message(f'🔑 Bandersnatch public: 0x{app.config.keys.bandersnatch.public_key.hex()}')
        info_message(f'🔑 Ed25519 public: 0x{app.config.keys.ed25519.public_key.hex()}')
        info_message(f'🗓️ Epoch: {app.config.epoch}')
        info_message(f'⏱️ Latest timeslot: #{app.state.timeslot.number}')

        lock = anyio.Lock()
        try:
            async with anyio.create_task_group() as tg:
                if block_dir:
                    tg.start_soon(timeslot_ticker, app, block_dir, traces_dir, lock)
                    info_message(f"👀 Watching directory: {block_dir} for new blocks...")
                    tg.start_soon(local_block_importer, app, block_dir, traces_dir, lock)
                else:
                    error_message("Networking not implemented yet; use --block-dir for filesystem mode")
        except (KeyboardInterrupt, CancelledError):
            info_message("Stopping node...")
        finally:
            info_message(f'Node stopped.')


async def store_trace(pre_state: dict, block: Block, output: STFOutput, app: PyjamazApp, traces_dir: str):
    trace = DeepDiff(pre_state, app.state.to_json(), ignore_order=True)

    trace_filepath = os.path.join(traces_dir, f'trace-{block.header.timeslot:06}.json')

    with open(trace_filepath, 'w') as file:
        json.dump(trace, file, indent=2)


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

                            # TODO keep state in memory
                            app.state = app.retrieve_jam_state()

                            data = json.load(file)
                            # TODO also import .bin jamcodec files
                            block = Block.from_json(data)

                            # TODO block.header.timeslot == 0 possible?
                            if block.header.timeslot > app.state.timeslot.number or app.state.timeslot.number == 0:

                                if traces_dir:
                                    pre_state = app.state.to_json()

                                output = await app.process_block(block)

                                if traces_dir:
                                    await store_trace(pre_state, block, output, app, traces_dir)

                                info_message(f"📦 Imported: {os.path.basename(filepath)}")
                            else:
                                info_message(f"⏭️ Skipped: {os.path.basename(filepath)}")

                except Exception as e:
                    error_message(f"Failed to process {filepath}: {e}")

            # Update the seen_files set to include the newly processed files
            seen_files.update(new_files)

        await anyio.sleep(.5)


async def timeslot_ticker(app: PyjamazApp, block_dir, traces_dir, lock):

    info_message(f'💤 Waiting to start at {datetime.fromtimestamp(app.config.epoch).strftime("%Y-%m-%d %H:%M:%S")}')
    await anyio.sleep(app.config.epoch - time.time())

    while True:

        if app.should_produce_block():
            async with lock:
                # TODO keep state in memory
                app.state = app.retrieve_jam_state()

                if traces_dir:
                    pre_state = app.state.to_json()

                block = await app.produce_block()
                output = await app.process_block(block, validate=False)
                await app.finalize_block(block, output)

                if traces_dir:
                    await store_trace(pre_state, block, output, app, traces_dir)

                # write block to dir
                filepath = os.path.join(block_dir, f'block-{block.header.timeslot:06}.json')
                with open(filepath, 'w') as file:
                    json.dump(block.to_json(), file, indent=2)

                info_message(f'🎁 Produced block: #{block.header.timeslot}')
        else:
            info_message(f'💤 Waiting for block #{app.current_timeslot()}')

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
async def init(initial_state, custom_db_path):
    """
    Clears all existing data and initializes the JAM client.

    Defaults to DEV initial state if none is provided.
    """

    db_path = custom_db_path or default_db_path

    if os.path.isdir(db_path):
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


@main.command()
async def debug():
    """
    Enters a debug prompt after initializing the app
    """

    def show(item):
        click.echo(json.dumps(item.to_json(), indent=2))

    def fields(item):
        click.echo(json.dumps(list(item.__dict__.keys()), indent=2))

    app = initialize_app()
    click.secho(f'=' * 80, bold=True)
    click.secho(f'PyJAMaz version: {__version__}', bold=True)
    click.secho(f'Python version: {sys.version}', bold=True)
    click.secho(f'DB direcory: {default_db_path}', bold=True)
    click.secho(f'Timeslot: {app.state.timeslot.number}', bold=True)
    click.secho(f'=' * 80, bold=True)
    click.echo(f"Entering debug mode.. \n")
    click.echo(f"* To quit, press 'q' and Enter")
    click.echo(f"* To print a serializable variable, use e.g. 'show(app.state.timeslot)'")
    click.echo(f"* To list fields of a dataclass, use e.g. 'fields(app.state)'")
    click.secho('_' * 80)
    import pdb
    pdb.set_trace()


if __name__ == '__main__':
    main(_anyio_backend="asyncio")
