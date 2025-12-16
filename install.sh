#!/bin/bash

set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

if ! [ -d .venv ]; then
    ${PY:-python3} -m venv .venv
    .venv/bin/pip3 install -r requirements.txt -i https://mirror.tuna.tsinghua.edu.cn/pypi/web/simple
fi

if ! [ -d bin ]; then
    sudo apt update
    sudo apt install libseccomp-dev -y
    sudo apt install libcap-dev -y
    .venv/bin/python3 build.py
fi

chmod +x run.sh

.venv/bin/python3 src/install.py
