#!/usr/bin/env bash
set -e

pip install -r requirements.txt
mkdir -p "${MEDIA_ROOT:-${RENDER_MEDIA_ROOT:-/var/data/media}}" || true
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py create_superuser_env || echo "create_superuser_env falhou ou ja existe — continuando."
