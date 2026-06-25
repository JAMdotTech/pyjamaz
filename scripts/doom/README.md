python pyjamaz/cli.py init --seed 0x0000000000000000000000000000000000000000000000000000000000000000 --force-overwrite --import-trace ./scripts/doom/doom-clean.bin
python pyjamaz/cli.py run --seed 0x0000000000000000000000000000000000000000000000000000000000000000 --host 0.0.0.0 --port 9000 --d3l-path=data/d3l
./scripts/doom/corevm-builder c36351c2  
./scripts/doom/corevm-monitor c36351c2  
