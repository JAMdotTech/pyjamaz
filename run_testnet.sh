clear
docker compose -p testnet down
# Remove previous data
#docker volume rm testnet_pyjamaz-blocks
rm -rf ./data/blocks/*
rm -rf ./data/traces-alice/*
rm -rf ./data/traces-bob/*
rm -rf ./data/traces-charlie/*
rm -rf ./data/traces-dave/*
rm -rf ./data/traces-eve/*
rm -rf ./data/traces-ferdie/*

docker compose -p testnet -f docker-compose-init.yml up --build --remove-orphans
docker compose -p testnet up --remove-orphans
