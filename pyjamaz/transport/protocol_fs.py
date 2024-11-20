async def file_block_importer(app: PyjamazApp, block_dir, traces_dir, lock):

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