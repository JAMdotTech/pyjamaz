clear
docker compose -p testnet2 down
# Remove previous data
#docker volume rm testnet_pyjamaz-blocks
rm -rf ./data/blocks/*
rm -rf ./data/traces-alice/*
rm -rf ./data/traces-bob/*
rm -rf ./data/traces-charlie/*
rm -rf ./data/traces-dave/*
rm -rf ./data/traces-eve/*
rm -rf ./data/traces-ferdie/*

docker compose -p testnet2 -f docker-compose-init.yml up --build --remove-orphans
docker compose -p testnet2 up --remove-orphans
