#!/bin/sh
set -e

cd /workdir

# -u forces unbuffered stdout/stderr so logs appear immediately in docker logs.
exec python3 -u ./supervisor.py
