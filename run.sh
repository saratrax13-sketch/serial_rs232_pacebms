#!/bin/sh
set -e

cd /workdir

echo "Starting PaceBMS web configuration UI..."
python3 -u ./web_config.py &

echo "Starting PaceBMS monitor..."

# -u forces unbuffered stdout/stderr so logs appear immediately in docker logs
exec python3 -u ./bms_monitor.py
