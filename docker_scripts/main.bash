#!/bin/bash
set -e

cd /docker/http
python server.py &

cd ${HOME}
source ./venv/bin/activate
python3 /docker/main.py
