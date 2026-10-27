# Все команды выполняются внутри Docker, поэтому локально нужен только Docker.
COMPOSE = docker compose
RUN = $(COMPOSE) run --rm web

.PHONY: env build up down logs test lint fmt seed digests shell

# На Windows интерпретатор обычно называется python, а на macOS и многих Linux есть только python3.
ifeq ($(OS),Windows_NT)
PYTHON = python
else
PYTHON = python3
endif

# Создать .env из примера, если его ещё нет. Через Python, а не cp,
# чтобы работало и в Linux/macOS, и в Windows (там make запускает cmd.exe).
env:
	@$(PYTHON) -c "import os, shutil; os.path.exists('.env') or shutil.copy('.env.example', '.env')"

build: env
	$(COMPOSE) build

up: env
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f celery web

test: env
	$(RUN) pytest

# --no-deps: линтеру не нужны БД и Redis.
lint: env
	$(COMPOSE) run --rm --no-deps web sh -c "ruff check . && ruff format --check ."

fmt: env
	$(COMPOSE) run --rm --no-deps web sh -c "ruff check --fix . && ruff format ."

seed:
	$(COMPOSE) exec web python manage.py seed_demo

digests:
	$(COMPOSE) exec web python manage.py send_digests

shell:
	$(COMPOSE) exec web python manage.py shell
