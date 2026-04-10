#!/usr/bin/env bash
set -e

pip install -r requirements.txt
MEDIA_TARGET="${MEDIA_ROOT:-${RENDER_MEDIA_ROOT:-}}"
if [ -z "$MEDIA_TARGET" ] && [ -n "${RENDER_DISK_PATH:-}" ]; then
	MEDIA_TARGET="${RENDER_DISK_PATH}/media"
fi
if [ -z "$MEDIA_TARGET" ] && [ -d "/var/data" ] && [ -w "/var/data" ]; then
	MEDIA_TARGET="/var/data/media"
fi
if [ -z "$MEDIA_TARGET" ]; then
	MEDIA_TARGET="media"
fi
mkdir -p "$MEDIA_TARGET" || true
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py create_superuser_env || echo "create_superuser_env falhou ou ja existe — continuando."
