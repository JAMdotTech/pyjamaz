import json
import os
from os import path

import click

from pyjamaz.app import PyjamazApp, AppConfig
from pyjamaz.storage import JSONStorage, LevelDBStorage
from pyjamaz.types.block import Block
from pyjamaz.types.state import JamState


def initialize_app(initial_state: JamState) -> PyjamazApp:
    data_dir = path.join(path.dirname(path.abspath(__file__)), 'data')
    with open(path.join(data_dir, 'zcash-srs-2-11-uncompressed.bin'), 'rb') as fp:
        ring_data = fp.read()

    # Initialize app
    config = AppConfig(
        ring_data=ring_data,
        # storage_engine=JSONStorage(path.join(data_dir, 'storage.json'))
        storage_engine=LevelDBStorage(path.join(data_dir, 'db'))
    )

    app = PyjamazApp(config=config)
    app.init_state(initial_state)
    return app


@click.group()
def main():
    """Python Jam Client"""
    pass


@main.command()
@click.argument('initial-state-json')
@click.argument('block-dir')
def import_blocks(initial_state_json, block_dir):
    """Import block data from a folder"""

    with open(path.join(os.getcwd(), initial_state_json), 'r') as fp:
        state_data = json.load(fp)

    jam_state = JamState.from_json(state_data)
    app = initialize_app(jam_state)

    # Process blocks
    for filename in sorted(os.listdir(block_dir)):
        if filename.endswith('.json'):
            with open(os.path.join(block_dir, filename)) as f:
                block_data = json.load(f)
            block = Block.from_json(block_data)
            app.state_transition(block)

            click.echo("Processed block {}".format(filename))

    click.echo('Import completed.')


if __name__ == '__main__':
    main()
