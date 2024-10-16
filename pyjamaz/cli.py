import json
import os
import shutil
import time
from os import path

import click

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from pyjamaz import __version__
from pyjamaz.app import PyjamazApp, AppConfig
from pyjamaz.storage import LevelDBStorage, InMemoryStorage
from pyjamaz.models.block import Block
from pyjamaz.models.state import JamState

data_dir = path.join(path.dirname(path.abspath(__file__)), 'data')
db_path = path.join(data_dir, 'db')


def error_message(message: str):
    click.echo(click.style(f'⚠️ {message}', fg='red'), err=True)


class JSONFileHandler(FileSystemEventHandler):
    def __init__(self, app):
        self.app = app  # Store the app instance for use in event handling

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            self.process_json(event.src_path)

    def process_json(self, filepath):
        try:
            with open(filepath, 'r') as file:
                data = json.load(file)
                block = Block.from_json(data)
                self.app.process_block(block)
                click.echo(f"🆕 Processed: {os.path.basename(filepath)}")
        except Exception as e:
            error_message(f"Failed to process {filepath}: {e}")


def initialize_app(read_state=True, memory_storage=False) -> PyjamazApp:
    with open(path.join(data_dir, 'zcash-srs-2-11-uncompressed.bin'), 'rb') as fp:
        ring_data = fp.read()

    try:
        if memory_storage:
            storage_engine = InMemoryStorage()
        else:
            storage_engine = LevelDBStorage(db_path)

    except IOError as e:
        error_message(f'Could not initialize storage engine: {str(e)}')
        exit(2)

    # Initialize app
    config = AppConfig(
        ring_data=ring_data,
        storage_engine=storage_engine
    )

    app = PyjamazApp(config=config)
    if read_state:
        app.state = app.retrieve_jam_state()

    return app


def process_blocks(app, block_dir):
    for filename in sorted(os.listdir(block_dir)):
        if filename.endswith('.json'):
            try:
                with open(os.path.join(block_dir, filename)) as f:
                    block_data = json.load(f)

                block = Block.from_json(block_data)
                app.process_block(block)

                click.echo("🆗 Processed: {}".format(filename))
            except Exception as e:
                error_message(f"Failed to process '{filename}': {e}")


# CLI commands

@click.group()
@click.version_option(package_name='pyjamaz')
def main():
    """PyJAMaz: Python JAM Client"""
    pass


@main.command()
@click.option('--initial-state-json', type=click.Path(exists=True))
def init(initial_state_json):
    """
    Clears all existing data and initializes the JAM client.

    Defaults to DEV initial state if none is provided.
    """
    if os.path.isdir(db_path):
        click.confirm(f"Database already exists at '{db_path}', delete?", abort=True)
        shutil.rmtree(db_path)  # Delete the directory if it exists
        click.echo(f"The database at '{db_path}' was deleted successfully.")

    if initial_state_json is None:
        state_file_name = path.join(data_dir, 'initial_state_template.json')
    else:
        state_file_name = initial_state_json

    with open(state_file_name, 'r') as fp:
        state_data = json.load(fp)

    jam_state = JamState.from_json(state_data)

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
def dump_state(output_format):
    """
    Dumps current state to stdout

    """
    app = initialize_app()

    if output_format == 'json':
        click.echo(json.dumps(app.state.to_json(), indent=2))
    elif output_format == 'bin':
        click.echo(app.state.to_jam_bytes().to_bytes(), file=click.get_binary_stream('stdout'), nl=False)


@main.command()
def debug():
    """
    Enters a debug prompt after initializing the app
    """
    app = initialize_app()
    click.echo(f'PyJAMaz version: {__version__}')
    click.echo(f'DB direcory: {db_path}')
    click.echo(f'Entering debug mode..')
    import pdb
    pdb.set_trace()


@main.command('import')
@click.argument('block-dir', type=click.Path(exists=True))
@click.option('--initial-state', type=click.File())
@click.option('--dry-run', is_flag=True, help="Perform a dry run without making any changes.")
@click.option('--watch', is_flag=True, help="Watches provided folder for new block data")
def import_blocks(block_dir, initial_state, dry_run, watch):
    """
    Import block data from folder BLOCK_DIR

    When --watch is provided, it will keep watching for new block data until keyboard interupt is given.
    """
    if initial_state:
        state_data = json.load(initial_state)

        jam_state = JamState.from_json(state_data)
        app = initialize_app(read_state=False, memory_storage=dry_run)
        app.store_jam_state(jam_state)
    else:
        if dry_run:
            error_message('Cannot perform dry run if no initial state is provided.')
            exit(2)
        app = initialize_app()

    # Process blocks
    process_blocks(app, block_dir)

    if watch:
        event_handler = JSONFileHandler(app)
        observer = Observer()
        observer.schedule(event_handler, block_dir, recursive=False)
        observer.start()
        click.echo(f"👀 Watching directory: {block_dir} for new JSON files...")

        try:
            while True:
                time.sleep(1)  # Keep the script running
        except KeyboardInterrupt:
            click.echo("✋Stopping directory watcher...")
            observer.stop()
        observer.join()
    else:
        click.echo('Import completed.')


if __name__ == '__main__':
    main()
