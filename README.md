# pyJAMaz
a Python implementation of the [JAM protocol](https://graypaper.com/).

## Install from source

```bash
pip install .
```

## Using the CLI

### Run JAM testnet

#### Alice
```bash
pyjamaz init --db-path ~/data/client0
pyjamaz --seed 0x0000000000000000000000000000000000000000000000000000000000000000 --block-dir ~/data/blocks --traces-dir ~/data/traces --db-path=~/data/client0 --ts 1730452890
```
#### Bob
```bash
pyjamaz init --db-path ~/data/client1
pyjamaz --seed 0x0000000000000000000000000000000000000000000000000000000000000001 --block-dir ~/data/blocks --traces-dir ~/data/traces --db-path=~/data/client1 --ts 1730452890
```
#### Charlie
```bash
pyjamaz init --db-path ~/data/client2
pyjamaz --seed 0x0000000000000000000000000000000000000000000000000000000000000002 --block-dir ~/data/blocks --traces-dir ~/data/traces --db-path=~/data/client2 --ts 1730452890
```

#### Dave
```bash
pyjamaz init --db-path ~/data/client3
pyjamaz --seed 0x0000000000000000000000000000000000000000000000000000000000000003 --block-dir ~/data/blocks --traces-dir ~/data/traces --db-path=~/data/client3 --ts 1730452890
```

#### Eve
```bash
pyjamaz init --db-path ~/data/client4
pyjamaz --seed 0x0000000000000000000000000000000000000000000000000000000000000004 --block-dir ~/data/blocks --traces-dir ~/data/traces --db-path=~/data/client4 --ts 1730452890
```

#### Ferdie
```bash
pyjamaz init --db-path ~/data/client5
pyjamaz --seed 0x0000000000000000000000000000000000000000000000000000000000000005 --block-dir ~/data/blocks --traces-dir ~/data/traces --db-path=~/data/client5 --ts 1730452890
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

