#!/bin/bash
# Lightweight TCP wait helper
# Usage: ./wait-for-it.sh host:port [-- command args]

TIMEOUT=60
HOST=""
PORT=""

parse_address() {
  local addr=$1
  HOST="${addr%%:*}"
  PORT="${addr##*:}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    *:* ) parse_address "$1"; shift ;;
    --  ) shift; break ;;
    *   ) shift ;;
  esac
done

echo "⏳ Waiting for $HOST:$PORT..."
for i in $(seq 1 $TIMEOUT); do
  if bash -c "echo > /dev/tcp/$HOST/$PORT" 2>/dev/null; then
    echo "✅ $HOST:$PORT is up"
    exec "$@"
    exit 0
  fi
  sleep 1
done
echo "❌ Timeout waiting for $HOST:$PORT"
exit 1