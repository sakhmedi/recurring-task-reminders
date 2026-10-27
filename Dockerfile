FROM python:3.12-slim

# Не создавать .pyc и сразу выводить логи (без буферизации) — удобно в Docker.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Сначала ставим только зависимости: этот слой кэшируется,
# пока не меняется pyproject.toml.
COPY pyproject.toml ./
RUN pip install ".[dev]"

COPY . .

EXPOSE 8000
CMD ["sh", "./entrypoint.sh"]
