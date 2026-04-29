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
* Fellowship Rank II nomination: [Matthijs Blaas](https://github.com/matthijsb)

## License
https://github.com/JAMdotTech/pyjamaz/blob/main/LICENSE
