"""Celery-приложение проекта.

Запуск:
    celery -A config worker -l info   # выполняет задачи
    celery -A config beat -l info     # по расписанию кладёт задачи в очередь
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")

# Все настройки Celery читаем из settings.py — те, что начинаются с CELERY_
# (например, CELERY_BROKER_URL -> broker_url).
app.config_from_object("django.conf:settings", namespace="CELERY")

# Ищем модуль tasks.py во всех приложениях из INSTALLED_APPS.
app.autodiscover_tasks()
