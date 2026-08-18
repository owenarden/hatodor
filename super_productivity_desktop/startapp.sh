#!/bin/sh
set -eu

python3 /opt/sp_proxy.py &
proxy_pid=$!

cleanup() {
    kill "${proxy_pid}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

exec /usr/bin/superproductivity \
    --ozone-platform=x11 \
    --disable-dev-shm-usage \
    --disable-gpu \
    --no-sandbox
