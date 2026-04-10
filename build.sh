#!/usr/bin/env bash
set -e

pip install -r requirements.txt

IS_RENDER_ENV=false
if [ -n "${RENDER_EXTERNAL_HOSTNAME:-}" ] || [ "${RENDER:-}" = "true" ]; then
  IS_RENDER_ENV=true
fi

MEDIA_TARGET="${MEDIA_ROOT:-${RENDER_MEDIA_ROOT:-}}"
if [ -z "$MEDIA_TARGET" ] && [ -n "${RENDER_DISK_PATH:-}" ]; then
	MEDIA_TARGET="${RENDER_DISK_PATH}/media"
fi
if [ -z "$MEDIA_TARGET" ] && [ -d "/var/data" ] && [ -w "/var/data" ]; then
	MEDIA_TARGET="/var/data/media"
fi
USING_EPHEMERAL_MEDIA=false
if [ -z "$MEDIA_TARGET" ]; then
	MEDIA_TARGET="media"
	USING_EPHEMERAL_MEDIA=true
fi

REQUIRE_PERSISTENT_MEDIA="${MEDIA_PERSISTENCE_REQUIRED_ON_RENDER:-false}"
REQUIRE_PERSISTENT_MEDIA="$(printf '%s' "$REQUIRE_PERSISTENT_MEDIA" | tr '[:upper:]' '[:lower:]')"

if [ "$IS_RENDER_ENV" = "true" ] && [ "$USING_EPHEMERAL_MEDIA" = "true" ] && [ "$REQUIRE_PERSISTENT_MEDIA" = "true" ]; then
  echo "ERRO: disco persistente de media nao encontrado no Render."
  echo "Configure MEDIA_ROOT, RENDER_MEDIA_ROOT ou RENDER_DISK_PATH para evitar perda de imagens."
  exit 1
fi

mkdir -p "$MEDIA_TARGET" || true
python manage.py collectstatic --no-input
python manage.py migrate
DJANGO_SUPERUSER_EMAIL="${DJANGO_SUPERUSER_EMAIL:-admin@easyschedule.com}" \
DJANGO_SUPERUSER_USERNAME="${DJANGO_SUPERUSER_USERNAME:-admin}" \
DJANGO_SUPERUSER_PASSWORD="${DJANGO_SUPERUSER_PASSWORD:-Adminadmin}" \
DJANGO_SUPERUSER_RESET_PASSWORD="${DJANGO_SUPERUSER_RESET_PASSWORD:-true}" \
python manage.py create_superuser_env
