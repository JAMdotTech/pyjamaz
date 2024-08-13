# pyJAMaz
a Python implementation of the [JAM protocol](https://graypaper.com/).

## Install from source

```bash
pip install .
```

## Using the CLI

### Import blocks
Initialize a new pyJAMaz app with provided initial state and import blocks from given folder.

Output will be a dump of the final state

```bash
pyjamaz import-blocks ./test/fixtures/cli/initial-state.json ./test/fixtures/cli/block_data > final_state.json
```

## Run documentation

```bash
pip install ".[dev]"
mkdocs serve
```

