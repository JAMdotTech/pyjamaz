import asyncio
import logging
import json
import os
from pathlib import Path

import argparse

import anyio
import time
from os import path

import asyncclick as click

from jamcodec.base import JamBytes

from pyjamaz.cli import initialize_app, process_state_diff
from pyjamaz import settings

from pyjamaz.logger import setup_logging
from pyjamaz.models.app import Trace
from pyjamaz.models.block import Header
from pyjamaz.utils import format_hash

data_dir = path.join(path.dirname(path.abspath(__file__)), 'data')
default_db_path = path.join(data_dir, 'db')


async def main(traces_dir:str):
    log_level = logging.DEBUG
    setup_logging(log_level)

    # Safety checks
    if settings.SOLO_MODE:
        raise Exception("settings.SOLO_MODE should be False when running traces")

    # Set GP relaxation flags
    settings.SKIP_TIMESLOT_WALL_CLOCK_CHECK = True

    app = await initialize_app(read_state=False, custom_db_path=None, storage_engine='memory', pubsub=False)

    traces_folder = Path(traces_dir)

    traces_files = await anyio.to_thread.run_sync(
        lambda: sorted({f for f in list(traces_folder.rglob("*.bin")) if f.name not in ['genesis.bin', 'report.bin']}),
    )

    last_parent = None

    start_time = time.time()

    # Process files in traces folder
    for nr, block_file in enumerate(traces_files, start=1):
        logging.info(f'📂 Processing trace file {block_file}')

        with open(os.path.join(traces_dir, block_file), 'rb') as fp:
            trace = Trace.from_jam_bytes(JamBytes(fp.read()))

        if trace.pre_state.state_root == bytes(32):
            # Skip genesis creation
            continue

        if block_file.parent != last_parent:

            # Flush DB
            for key, _ in app.state_db.as_list():
                app.state_db.delete(key)

            # Clear pending changesets
            # app.historical_state.clear()

            # Add stub parent as ancestor TODO still needed?
            stub_parent = Header.default()
            stub_parent.hash = trace.block.header.parent
            stub_parent.timeslot = trace.block.header.timeslot - 1

            # Set finalized head
            app.state_storage.set_finalized_block_hash(stub_parent.hash)

            # Update state from trace pre-state
            for k, v in trace.pre_state.keyvals:
                app.state_db.put(bytes(k), bytes(v))

            # Add stub
            await app.store_block_header(stub_parent)
            await app.add_ancestor_header(stub_parent)

            # Store block
            await app.store_block(trace.block)
            await app.add_ancestor_header(trace.block.header)

            await app.initialize(header=trace.block.header)

            if app.working_state.state_root == trace.pre_state.state_root:
                logging.info(
                    f'🎬 Pre-state successfully saved (state root: {format_hash(app.working_state.state_root)})'
                    )
            else:
                logging.error("State root of pre-state doesn't match")

            last_parent = block_file.parent

        logging.info(
            f'⚙️ Processing block {trace.block.header.timeslot} (hash={format_hash(trace.block.header.hash)} parent={format_hash(trace.block.header.parent)} parent_state_root={format_hash(trace.block.header.parent_state_root)})'
            )

        # Finalize parent
        app.state_storage.finalize(trace.block.header.parent)

        # Import block
        await app.import_block(trace.block)

        logging.info(f'✅ Block {trace.block.header.timeslot} successfully imported.')

        # Validate new state root
        if app.working_state.state_root == trace.post_state.state_root:
            logging.info(f'✅ State trie root matches ({format_hash(trace.post_state.state_root)})')
        else:
            logging.error(
                f'State root of trace {format_hash(trace.post_state.state_root)} does not match with current state {format_hash(app.working_state.state_root)}'
                )

            # Diffing DBs
            process_state_diff(app.state_storage.as_list(), trace.post_state.keyvals)

            if nr < len(traces_files):
                response = click.prompt("Press Enter to continue or type 'q' to quit", default='', show_default=False)
                if response.lower() == 'q':
                    logging.info('✋ User aborted.')
                    break

    logging.info(f'Traces finished in {time.time() - start_time} seconds')



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("traces_dir", help="path to traces to run")
    args = parser.parse_args()
    if not args.traces_dir:
        raise Exception("Please provide path to traces to run")

    asyncio.run(main(traces_dir=args.traces_dir))
