#!/bin/bash

set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

sudo apt update
sudo apt install libseccomp-dev -y
sudo apt install libcap-dev -y

${PY:-python3} -m venv .venv
source .venv/bin/activate

pip3 install -r requirements.txt -i https://mirror.tuna.tsinghua.edu.cn/pypi/web/simple

python3 build.py

chmod +x run.sh

if [ -f ~/.bash_aliases ]; then
    cp ~/.bash_aliases ~/.bash_aliases.bak
    echo "原 ~/.bash_aliases 已备份到 ~/.bash_aliases.bak"
fi
echo "alias selfeval=\"$(pwd)/run.sh\"" >> ~/.bash_aliases
if [ -f ~/.bashrc ]; then
    source ~/.bashrc
fi
