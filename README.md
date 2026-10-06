# pyJAMaz
a Python implementation of the [JAM protocol](https://graypaper.com/).

## Install from source

```bash
pip install .
```

## Run fuzzer target
```bash
pyjamaz fuzzer target --socket-path=/tmp/jam_target.sock
```

## Running fuzzer target using Docker
docker run -v /tmp:/tmp \
           -e JAM_FUZZ=1 \
           -e JAM_FUZZ_SPEC=tiny \
           -e JAM_FUZZ_DATA_PATH=/tmp/pyjamaz_data/ \
           -e JAM_FUZZ_SOCK_PATH=/tmp/jam_target.sock \
           -e JAM_FUZZ_LOG_LEVEL=info \
           jamdottech/pyjamaz:latest

## Build and publish multi-arch Docker image
```bash
docker buildx create --name multiarch-builder --use
docker buildx inspect --bootstrap
docker buildx build --platform linux/amd64,linux/arm64 -t jamdottech/pyjamaz -t jamdottech/pyjamaz:vX.Y.Z-gpX.Y.Z --push .
```

## JAM prize M1 accounts
* Polkadot: 146CmUoArEi1E2AogKCU5gkhBSN6BLDzxecFSCDAgVyEshra
* Kusama: DBPAKp9B2gpBr9YmvqXyewYkR4ZwTn9uJDt64zGcVjZeiGi

## Fellowship M1 nominations
* Fellowship Rank III nomination: [Arjan Zijderveld](https://github.com/arjanz)
* Fellowship Rank II nomination: [Emiel Sebastiaan](https://github.com/emielsebastiaan)

## License
https://github.com/JAMdotTech/pyjamaz/blob/main/LICENSE

## Graypaper 0.8 PVM tests

The default instruction suite uses the updated `graypaper-gas-3/pvm/programs`
fixtures, copied unchanged into `test/fixtures/pvm/gas-cost`. The upstream
`gas-tests` fixtures are in `test/fixtures/pvm/integration-tests` and check block
costs for Doom, Pinky, and prime-sieve without executing those programs.

Run from the repository root with the project dependencies installed:

```bash
python -m pytest test/test_pvm_instructions.py -q
PVM_TEST_VECTORS=fixtures/pvm/integration-tests/ python -m pytest test/test_pvm_instructions.py -q
python -m pytest test/test_graypaper_08.py test/test_pvm_gas_regressions.py test/test_pvm_memory.py test/test_cpython_mmap_memory.py test/test_hostcalls_general.py test/test_hostcalls_accumulate.py -q
```

Set `PVM_INTERPRETER` to `GRAYPAPER`, `CPYTHON`, `NUMBA_JIT`, or `NUMBA_AOT`
(the default) to select a backend. Rebuild precompiled Numba caches when deploying
this change; `NUMBA_CACHE_DIR` can select an empty directory for verification.

This PVM uses the 0.8 opcode and hostcall numbering, `grow_heap`, and the hostcall
gas schedule in Appendix I.4.5. Programs built against the earlier ABI must be
rebuilt. The interpreter's `pc` retains the stopping instruction for diagnostics
and the supplied vector format; host invocation results and saved inner-VM state
return zero for a final halt or panic, as specified by Appendix A.1.
