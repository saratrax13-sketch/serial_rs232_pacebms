#!/bin/sh
set -e

cd /workdir

# Home Assistant creates /data/options.json for add-ons. Standalone Docker does
# not, so this helper creates it once from config.yaml defaults plus env vars.
python3 -u ./standalone_config.py

# -u forces unbuffered stdout/stderr so logs appear immediately in docker logs.
exec python3 -u ./supervisor.py
