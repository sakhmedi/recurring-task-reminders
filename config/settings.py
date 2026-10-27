"""Настройки проекта. Всё, что зависит от окружения, читается из переменных окружения."""

import os
from pathlib import Path

from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent


def env_list(name: str, default: str = "") -> list[str]:
    """Читает список из переменной окружения вида "a,b,c"."""
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# SECRET_KEY не храним в коде: без переменной окружения проект не запустится.
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "reminders",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "reminders"),
        "USER": os.environ.get("POSTGRES_USER", "reminders"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "reminders"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Время -------------------------------------------------------------------
# В БД время хранится в UTC (USE_TZ=True), а "сегодня" считаем по Алматы
# через timezone.localdate().
LANGUAGE_CODE = "ru"
TIME_ZONE = "Asia/Almaty"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

# Куда отправлять неавторизованных со страницы /upcoming/.
LOGIN_URL = "admin:login"

# --- Почта ---------------------------------------------------------------------
# Для демо письма просто печатаются в stdout (видно в docker compose logs).
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "reminders@example.com")

# --- Celery -------------------------------------------------------------------
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
# Результаты задач нам не нужны — число писем видно в логах воркера.
CELERY_TASK_IGNORE_RESULT = True
# Расписание beat интерпретируется в этой зоне: 09:00 — это 09:00 по Алматы.
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "daily-digest": {
        "task": "reminders.tasks.send_due_digests",
        "schedule": crontab(hour=9, minute=0),
        "kwargs": {"days_ahead": 3},
    },
}

# --- Логи ---------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    # propagate=False: не передавать записи корневому логгеру, иначе в celery
    # (он настраивает свой корневой логгер) каждая строка печаталась бы дважды.
    "loggers": {"reminders": {"handlers": ["console"], "level": "INFO", "propagate": False}},
}
