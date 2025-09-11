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

    app = await initialize_app(read_state=False, custom_db_path=None, storage_engine='memory')

    traces_folder = Path(traces_dir)

    traces_files = await anyio.to_thread.run_sync(
        lambda: sorted({f for f in list(traces_folder.rglob("*.bin")) if f.name not in ['genesis.bin', 'report.bin']}),
    )

    start_time = time.time()

    for nr, block_file in enumerate(traces_files, start=1):
        logging.info(f'📂 Processing trace file {block_file}')

        with open(os.path.join(traces_dir, block_file), 'rb') as fp:
            trace = Trace.from_jam_bytes(JamBytes(fp.read()))

        if trace.pre_state.state_root == bytes(32):
            # Skip genesis creation
            continue

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

        logging.info(
            f'⚙️ Processing block {trace.block.header.timeslot} (hash: {format_hash(trace.block.header.hash)})')

        skip_block_validation=False
        await app.import_block(trace.block, dry_run=skip_block_validation)
        # Update Patricia Trie
        await app.update_state_trie()

        logging.info(f'✅ Block {trace.block.header.timeslot} successfully imported.')

        if app.state_trie_root == trace.post_state.state_root:
            logging.info(f'✅ State trie root matches ({format_hash(trace.post_state.state_root)})')
        else:
            logging.error(
                f'State root of trace {format_hash(trace.post_state.state_root)} does not match with current state {format_hash(app.state_trie_root)}')

            # Diffing DBs
            process_state_diff(list(app.state_db.items()), trace.post_state.keyvals)

            state_dump_file = f'state_{block_file.name.replace(".bin", "")}.json'

            with open(os.path.join(traces_dir, state_dump_file), 'w') as file:
                json.dump(app.state.to_json(), file, indent=2)
            logging.info(f"Current state written to disk: {state_dump_file}")

            # Update state from trace post-state
            for k, v in trace.post_state.keyvals:
                app.state_db.put(bytes(k), bytes(v))

            app.state = app.retrieve_jam_state()
            await app.update_state_trie()

            state_dump_file = f'trace_post_{block_file.name.replace(".bin", "")}.json'

            with open(os.path.join(traces_dir, state_dump_file), 'w') as file:
                json.dump(app.state.to_json(), file, indent=2)
            logging.info(f"Trace post-state written to disk: {state_dump_file}")

            if nr < len(traces_files):
                response = click.prompt("Press Enter to continue or type 'q' to quit", default='', show_default=False)
                if response.lower() == 'q':
                    logging.info('✋ User aborted.')
                    break

        # Flush DB
        for key, _ in app.state_db.items():
            app.state_db.delete(key)

    logging.info(f'Traces finished in {time.time() - start_time} seconds')



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("traces_dir", help="path to traces to run")
    args = parser.parse_args()
    if not args.traces_dir:
        raise Exception("Please provide path to traces to run")

    asyncio.run(main(traces_dir=args.traces_dir))
