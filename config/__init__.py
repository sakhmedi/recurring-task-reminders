# Импортируем Celery-приложение при старте Django, чтобы декоратор
# @shared_task привязывал задачи именно к нему.
from .celery import app as celery_app

__all__ = ("celery_app",)
