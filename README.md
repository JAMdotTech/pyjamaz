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

### Run JAM testnet

#### Alice
```bash
pyjamaz init --db-path ~/data/alice
pyjamaz --seed 0x0000000000000000000000000000000000000000000000000000000000000000 --block-dir ~/data/blocks --traces-dir ~/data/traces --db-path=~/data/alice --ts 1730452890
```
#### Bob
```bash
pyjamaz init --db-path ~/data/bob
pyjamaz --seed 0x0000000000000000000000000000000000000000000000000000000000000001 --block-dir ~/data/blocks --traces-dir ~/data/traces --db-path=~/data/bob --ts 1730452890
```
#### Charlie
```bash
pyjamaz init --db-path ~/data/charly
pyjamaz --seed 0x0000000000000000000000000000000000000000000000000000000000000002 --block-dir ~/data/blocks --traces-dir ~/data/traces --db-path=~/data/charly --ts 1730452890
```

#### Dave
```bash
pyjamaz init --db-path ~/data/dave
pyjamaz --seed 0x0000000000000000000000000000000000000000000000000000000000000003 --block-dir ~/data/blocks --traces-dir ~/data/traces --db-path=~/data/dave --ts 1730452890
```

#### Eve
```bash
pyjamaz init --db-path ~/data/eve
pyjamaz --seed 0x0000000000000000000000000000000000000000000000000000000000000004 --block-dir ~/data/blocks --traces-dir ~/data/traces --db-path=~/data/eve --ts 1730452890
```

#### Ferdie
```bash
pyjamaz init --db-path ~/data/ferdi
pyjamaz --seed 0x0000000000000000000000000000000000000000000000000000000000000005 --block-dir ~/data/blocks --traces-dir ~/data/traces --db-path=~/data/ferdi --ts 1730452890
```

### Generate validator keys

```bash
pyjamaz keys generate 0x0000000000000000000000000000000000000000000000000000000000000000

```

### Dump state to stdout

```bash
pyjamaz dump > state.json
```

### Show debug info and access state directly
```bash
pyjamaz debug
# > fields(app.state)
# > show(app.state.safrole)
```


## Run documentation

```bash
pip install ".[dev]"
mkdocs serve
```

