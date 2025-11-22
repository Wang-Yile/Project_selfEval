#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "$DIR/.venv" ]; then
    echo "Python 虚拟环境不存在！"
    echo "请按照 README.md 部署指南创建虚拟环境并安装依赖。"
    exit 1
fi

"$DIR/.venv/bin/python3" "$DIR/selfeval.py" "$@"
