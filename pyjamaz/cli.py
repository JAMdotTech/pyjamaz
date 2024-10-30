import asyncio
from datetime import datetime
import json
import os
import shutil
import random

import anyio
import math
import sys

import time
from os import path

import asyncclick as click
from asyncclick import BadParameter

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from jamcodec.base import JamBytes
from pyjamaz import __version__
from pyjamaz.app import PyjamazApp, AppConfig, Keys
from pyjamaz.graypaper_constants import SLOT_PERIOD
from pyjamaz.models.common import ValidatorData
from pyjamaz.models.stf_output import STFOutput
from pyjamaz.storage import LevelDBStorage, InMemoryStorage
from pyjamaz.models.block import Block
from pyjamaz.models.state import JamState

data_dir = path.join(path.dirname(path.abspath(__file__)), 'data')
db_path = path.join(data_dir, 'db')


def error_message(message: str):
    formatted_date_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    click.echo(
        click.style(formatted_date_time, fg=(80, 80, 80)) + '  ' + click.style(f'⚠️ {message}', fg='red'), err=True
    )


def info_message(message: str):
    formatted_date_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    click.echo(click.style(formatted_date_time, fg=(80, 80, 80)) + '  ' + message)


# class JSONFileHandler(FileSystemEventHandler):
#     def __init__(self, app, latest_output):
#         self.app = app  # Store the app instance for use in event handling
#         self.latest_output = latest_output
#
#     def on_created(self, event):
#         if not event.is_directory and event.src_path.endswith('.json'):
#             latest_output = self.process_json(event.src_path)
#             # Check if validator should produce block
#             # if self.app.should_produce_block():
#             #     block = self.app.produce_block(output)
#
#     def process_json(self, filepath):
#         try:
#             with open(filepath, 'r') as file:
#                 data = json.load(file)
#                 block = Block.from_json(data)
#                 output = self.app.process_block(block)
#                 info_message(f"🆕 Processed: {os.path.basename(filepath)}")
#                 return output
#         except Exception as e:
#             error_message(f"Failed to process {filepath}: {e}")


def initialize_app(read_state=True, memory_storage=False, keys=None, epoch=None) -> PyjamazApp:

    # Load SRS
    with open(path.join(data_dir, 'zcash-srs-2-11-uncompressed.bin'), 'rb') as fp:
        ring_data = fp.read()

    # Initiate storage engine
    try:
        if memory_storage:
            storage_engine = InMemoryStorage()
        else:
            storage_engine = LevelDBStorage.create_from_file(db_path)

    except IOError as e:
        error_message(f'Could not initialize storage engine: {str(e)}')
        exit(2)

    # Set epoch
    if not epoch:
        epoch = math.ceil(time.time() / 12) * 12

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


async def process_blocks(app, block_dir):
    for filename in sorted(os.listdir(block_dir)):
        if filename.endswith('.json'):
            try:
                with open(os.path.join(block_dir, filename)) as f:
                    block_data = json.load(f)

                block = Block.from_json(block_data)
                app.process_block(block)

                app.store_block(block)

                info_message("🆗 Processed: {}".format(filename))
            except Exception as e:
                error_message(f"Failed to process '{filename}': {e}")


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
async def main(ctx, seed, port, ts, mode, culprit, block_dir, traces_dir):
    """PyJAMaz: Python JAM Client"""

    if mode != 'safrole':
        raise BadParameter(f'{mode} is not supported yet')

    app = initialize_app(
        keys=Keys.from_seed(bytes.fromhex(seed[2:])),
        epoch=ts
    )

    if ctx.invoked_subcommand is None:
        info_message(f'🥋 Starting PyJAMaz client, listening on port {port}')
        info_message(f'🔑 Bandersnatch public: 0x{app.config.keys.bandersnatch.public_key.hex()}')
        info_message(f'🔑 Ed25519 public: 0x{app.config.keys.ed25519.public_key.hex()}')
        info_message(f'🗓️ Epoch: {app.config.epoch}')
        info_message(f'⏱️ Latest timeslot: #{app.state.timeslot.number}')


        latest_output = STFOutput()
        lock = anyio.Lock()

        async with anyio.create_task_group() as tg:
            if block_dir:
                tg.start_soon(timeslot_ticker, app, latest_output, block_dir, lock)
                info_message(f"👀 Watching directory: {block_dir} for new blocks...")
                tg.start_soon(local_block_importer, app, block_dir, traces_dir, latest_output, lock)
            else:
                error_message("Networking not implemented yet; use --block-dir for filesystem mode")

        info_message(f'Node stopped.')


# async def local_block_importer(app: PyjamazApp, block_dir, latest_output: STFOutput):
#     event_handler = JSONFileHandler(app, latest_output)
#     observer = Observer()
#     observer.schedule(event_handler, block_dir, recursive=False)
#     observer.start()
#     info_message(f"👀 Watching directory: {block_dir} for new blocks...")
#
#     try:
#         while True:
#             time.sleep(1)  # Keep the script running
#     except KeyboardInterrupt:
#         info_message("✋Stopping directory watcher...")
#         observer.stop()
#     observer.join()


async def process_file(filepath):
    # Your file processing logic here
    info_message(f"Processing file: {filepath}")
    # Simulate some async processing time
    await anyio.sleep(1)


async def local_block_importer(app: PyjamazApp, block_dir, traces_dir, latest_output: STFOutput, lock):
    # Track the files already in the directory
    seen_files = set()

    while True:
        # Run the directory check in a separate thread (non-blocking)
        new_files = await anyio.to_thread.run_sync(
            lambda: {f for f in os.listdir(block_dir) if f.endswith('.json')} - seen_files
        )

        if new_files:
            for filename in sorted(new_files):
                filepath = os.path.join(block_dir, filename)

                try:
                    with open(filepath, 'r') as file:
                        data = json.load(file)
                        block = Block.from_json(data)

                        trace = {'pre_state': app.state.to_json()}

                        output = await app.process_block(block)

                        app.store_block(block)

                        trace['output'] = output.to_json()
                        trace['post_state'] = app.state.to_json()

                        if traces_dir:
                            trace_filepath = os.path.join(traces_dir, f'trace-{block.header.timeslot:06}.json')

                            with open(trace_filepath, 'w') as file:
                                json.dump(trace, file, indent=2)

                        async with lock:
                            latest_output.epoch_mark = output.epoch_mark
                            latest_output.tickets_mark = output.tickets_mark
                            latest_output.offenders_mark = output.offenders_mark

                        info_message(f"📦 Imported: {os.path.basename(filepath)}")

                except Exception as e:
                    error_message(f"Failed to process {filepath}: {e}")

            # Update the seen_files set to include the newly processed files
            seen_files.update(new_files)

        # Wait for the specified interval before polling again
        await anyio.sleep(1)


async def timeslot_ticker(app: PyjamazApp, latest_output: STFOutput, block_dir, lock):

    try:
        while int(time.time()) < app.config.epoch:
            info_message(f'💤 Waiting to start at {app.config.epoch} (now is {int(time.time())})')
            await anyio.sleep(1)

        while True:

            if app.should_produce_block():
                async with lock:
                    block = app.produce_block(latest_output)
                    # write block to dir
                    filepath = os.path.join(block_dir, f'block-{block.header.timeslot:06}.json')
                    with open(filepath, 'w') as file:
                        json.dump(block.to_json(), file, indent=2)

                info_message(f'🎁 Produced block: #{block.header.timeslot}')
            else:
                info_message(f'💤 Waiting for blocks #{app.current_timeslot()}')

            await anyio.sleep(SLOT_PERIOD)

    except (KeyboardInterrupt, anyio.get_cancelled_exc_class()):
        info_message("Stopping node...")


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

    validator_data = ValidatorData(
        ed25519=validator_keys.ed25519.public_key,
        bandersnatch=validator_keys.bandersnatch.public_key,
        bls=bytes(144),
        metadata=bytes(128)
    )

    click.echo(json.dumps(validator_data.to_json(), indent=2))


@main.command()
@click.option('--initial-state', type=click.Path(exists=True))
async def init(initial_state):
    """
    Clears all existing data and initializes the JAM client.

    Defaults to DEV initial state if none is provided.
    """
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

    app = initialize_app(read_state=False)
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
    click.secho(f'DB direcory: {db_path}', bold=True)
    click.secho(f'Timeslot: {app.state.timeslot.number}', bold=True)
    click.secho(f'=' * 80, bold=True)
    click.echo(f"Entering debug mode.. \n")
    click.echo(f"* To quit, press 'q' and Enter")
    click.echo(f"* To print a serializable variable, use e.g. 'show(app.state.timeslot)'")
    click.echo(f"* To list fields of a dataclass, use e.g. 'fields(app.state)'")
    click.secho('_' * 80)
    import pdb
    pdb.set_trace()


# @main.command('import')
# @click.argument('block-dir', type=click.Path(exists=True))
# @click.option('--initial-state', type=click.File())
# @click.option('--export-state', type=click.File(mode='w'), help='Export the current state to a JSON-file')
# @click.option('--dry-run', is_flag=True, help="Perform a dry run without making any changes.")
# @click.option('--watch', is_flag=True, help="Watches provided folder for new block data")
# async def import_blocks(block_dir, initial_state, export_state, dry_run, watch):
#     """
#     Import block data from folder BLOCK_DIR
#
#     When --watch is provided, it will keep watching for new block data until keyboard interupt is given.
#     """
#     if initial_state:
#         app = initialize_app(read_state=False, memory_storage=dry_run)
#
#         if initial_state.name.endswith('.json'):
#             state_data = json.load(initial_state)
#             app.state = JamState.from_json(state_data)
#         elif initial_state.name.endswith('.bin'):
#             app.state = JamState.from_jam_bytes(JamBytes(initial_state.read_bytes()))
#         else:
#             raise BadParameter('initial_state can only be .json or .bin')
#
#         app.store_jam_state(app.state)
#     else:
#         app = initialize_app()
#
#         if dry_run:
#             # Re-initialize app with memory storage to perform dry-run
#             current_state = app.state
#             app = initialize_app(read_state=False, memory_storage=True)
#             app.store_jam_state(current_state)
#
#     # Process blocks
#     process_blocks(app, block_dir)
#
#     if watch:
#         event_handler = JSONFileHandler(app)
#         observer = Observer()
#         observer.schedule(event_handler, block_dir, recursive=False)
#         observer.start()
#         info_message(f"👀 Watching directory: {block_dir} for new JSON files...")
#
#         try:
#             while True:
#                 time.sleep(1)  # Keep the script running
#         except KeyboardInterrupt:
#             info_message("✋Stopping directory watcher...")
#             observer.stop()
#         observer.join()
#
#     if export_state:
#         json.dump(app.state.to_json(), export_state, indent=2)
#
#     if dry_run:
#         info_message('✅ Dry-run completed.')
#     else:
#         info_message('✅ Import completed.')


if __name__ == '__main__':
    main(_anyio_backend="asyncio")
