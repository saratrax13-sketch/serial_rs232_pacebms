#!/bin/sh
set -e

echo "Starting BMS Pace monitor..."

cd /workdir

# -u forces unbuffered stdout/stderr so logs appear immediately in docker logs
exec python3 -u ./bms_monitor.py
