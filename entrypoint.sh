#!/bin/sh
# Точка входа сервиса web: миграции -> суперюзер -> dev-сервер.
set -e

python manage.py migrate --noinput

# createsuperuser берёт логин/почту/пароль из DJANGO_SUPERUSER_* (см. .env.example).
# Если пользователь уже есть, команда падает — это нормально, поэтому "|| true".
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
    python manage.py createsuperuser --noinput || true
fi

exec python manage.py runserver 0.0.0.0:8000
