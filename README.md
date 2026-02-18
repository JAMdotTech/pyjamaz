# pyJAMaz
a Python implementation of the [JAM protocol](https://graypaper.com/).

## Install from source

```bash
pip install .
```

## Run fuzzer target
```bash
pyjamaz fuzzer target
```

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
