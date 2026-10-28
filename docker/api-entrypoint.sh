#!/bin/sh
# Root only long enough to hand /data to the app user, then drop privileges.
set -eu
mkdir -p /data
chown nia:nia /data
cd /app
exec su -s /bin/sh nia -c 'PATH="/app/.venv/bin:$PATH" exec fastapi run --host 0.0.0.0 --port 8000'
