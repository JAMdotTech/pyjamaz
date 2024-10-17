## Description
PyJAMaz is a Python implementation of the JAM protocol.

## What is JAM?

JAM is the Join-Accumulate Machine, a new protocol designed to succeed the Polkadot relay chain. It provides significantly enhanced smart contract functionality.

[Read more about JAM](https://graypaper.com/)

## Installation
```bash
pip install pyjamaz
```

## Run conformance test

```bash
pyjamaz init --initial-state-json=./initial-state.json
pyjamaz import ./block_data
pyjamaz dump > current_state.json
```
