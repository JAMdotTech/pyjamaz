# pyJAMaz
a Python implementation of the [JAM protocol](https://graypaper.com/).

## Install from source

```bash
pip install .
```

## Using the CLI

### Run conformance test
```bash
pyjamaz init --initial-state=./initial-state.json
pyjamaz import ./block_data
pyjamaz dump > current_state.json
```

### Import and watch for new block data
```bash
pyjamaz import ./block_data --watch
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

