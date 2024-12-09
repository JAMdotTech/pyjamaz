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
docker compose -p testnet up --remove-orphans
```
### Start in Detached Mode
```bash
docker compose -p testnet up -d --remove-orphans
```
### Stop
```bash
docker compose -p testnet down --remove-orphans
```


## Using the CLI

### Generate validator keys

```bash
pyjamaz keys generate 0x0000000000000000000000000000000000000000000000000000000000000000

```

### Initialize node 

```bash
pyjamaz init 
```

### Initialize node with custom [genesis.json](https://github.com/JAMdotTech/pyjamaz/blob/main/pyjamaz/data/genesis.json) 

```bash
pyjamaz init --genesis ./pyjamaz/data/genesis.json 
```

### Run node

```bash
pyjamaz --seed 0x0000000000000000000000000000000000000000000000000000000000000000 --block-dir ./data/blocks
```

### Run and record each block as a replayable file in given folder

```bash
pyjamaz --seed 0x0000000000000000000000000000000000000000000000000000000000000000 --block-dir ./data/blocks --record-trace ./data/trace
```

### Replay and validate a recorded trace

```bash
pyjamaz replay_traces ./test/fixtures/traces/pyjamaz
```

### Replay a recorded trace and skip block validation

```bash
pyjamaz replay_traces ./test/fixtures/traces/duna --skip-block-validation
```

### Replay a recorded trace and only import block data, skip pre-state import and post-state validation

```bash
pyjamaz replay_traces ./test/fixtures/traces/duna --only-block-import
```


### Dump current state to stdout

```bash
pyjamaz dump_state > state.json
```

### Dump block to stdout

```bash
pyjamaz dump_block 4849460
```

## Run documentation

```bash
pip install ".[dev]"
mkdocs serve
```

