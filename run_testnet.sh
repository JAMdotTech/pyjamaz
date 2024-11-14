clear
docker compose -p testnet down
docker volume rm testnet_pyjamaz-blocks
rm -rf ./data/blocks/*
docker compose -p testnet -f docker-compose-init.yml up --build --remove-orphans
docker compose -p testnet up --remove-orphans
