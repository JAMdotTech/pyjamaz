# pyJAMaz
a Python implementation of the [JAM protocol](https://graypaper.com/).

## Install from source

```bash
pip install .
```

## Using Docker to run JAM testnet 

### Initialize
```bash
docker compose -p testnet -f docker-compose-init.yml up --build --remove-orphans
```
### Start in Console Mode
```bash
docker compose -p testnet up --build --remove-orphans
```
### Start in Detached Mode
```bash
docker compose -p testnet up -d --build --remove-orphans
```
### Stop
```bash
docker compose -p testnet down --remove-orphans
```

### Start fuzzer target from Docker image
```bash
docker build . -t jamdottech/pyjamaz
docker run -it jamdottech/pyjamaz fuzzer_target --seed 0x0000000000000000000000000000000000000000000000000000000000000000  --socket_path /tmp/jam_target.sock --force-overwrite
```

## Using the CLI

### Generate validator data for use in genesis.json

```bash
pyjamaz keys generate 0x0000000000000000000000000000000000000000000000000000000000000000 127.0.0.1 9000

```

### Initialize node 

```bash
pyjamaz init --seed 0x0000000000000000000000000000000000000000000000000000000000000000 --chainspec dev
```

### Run node

```bash
pyjamaz --seed 0x0000000000000000000000000000000000000000000000000000000000000000 --host 0.0.0.0 --port 9000
```

### Run and record each block as a replayable file in given folder

```bash
pyjamaz --seed 0x0000000000000000000000000000000000000000000000000000000000000000 --record-trace ./data/trace
```

### Replay and validate a recorded trace

```bash
pyjamaz replay_traces ./test/fixtures/traces/pyjamaz --seed 0x0000000000000000000000000000000000000000000000000000000000000000
```

### Run as fuzzer target

```bash
pyjamaz fuzzer_target --seed 0x0000000000000000000000000000000000000000000000000000000000000000 --db-path /tmp/fuzzer --force-overwrite --socket_path /tmp/jam_target.sock
```

### Connect to a fuzzer target 
```bash
pyjamaz --seed 0x0000000000000000000000000000000000000000000000000000000000000000 --host 0.0.0.0 --port 9000 --fuzzer --fuzzer-socket-path /tmp/jam_target.sock
```

## Run documentation

```bash
pip install ".[dev]"
mkdocs serve
```

# Resources
* https://hackmd.io/@polkadot/jamsdk#JAM-Client-Tooling
* https://github.com/polkadot-fellows/JIPs
