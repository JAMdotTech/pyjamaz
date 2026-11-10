apt update
sudo apt update
apt upgrade
sudo apt upgrade
python3 -m venv venv

sudo apt-get update
sudo apt install python3.12-venv unzip

# Docker
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do sudo apt-get remove $pkg; done
# Add Docker's official GPG key:
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
# Add the repository to Apt sources:
echo   "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" |   sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker

# Clone repos
git clone https://github.com/davxy/jam-test-vectors.git
git clone https://github.com/davxy/jam-conformance.git

# Setup fuzzer
python3 -m venv venv
. venv/bin/activate
pip install ~/jam-conformance/scripts/targets/pyjamaz/latest/gp-0.7.0/pyjamaz-0.1.5-cp312-none-any.whl

# Install targets
~/jam-conformance/scripts/target.sh get jamzig

# Run target
~/jam-conformance/scripts/target.sh run jamzig

# Run fuzzer
pyjamaz fuzzer traces /home/ubuntu/jam-test-vectors/traces/fallback/
pyjamaz fuzzer traces /home/ubuntu/jam-test-vectors/traces/safrole/
pyjamaz fuzzer traces /home/ubuntu/jam-test-vectors/traces/storage_light/
pyjamaz fuzzer traces /home/ubuntu/jam-test-vectors/traces/preimages_light/
pyjamaz fuzzer traces /home/ubuntu/jam-test-vectors/traces/storage/
pyjamaz fuzzer traces /home/ubuntu/jam-test-vectors/traces/preimages/
