"""Демо-данные: 3 компании, 10 задач с разными сроками относительно сегодняшнего дня.

Команду можно запускать повторно: задачи демо-компаний пересоздаются.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from reminders.models import Company, Task

OPS = "ops@example.com"
DEV = "dev@example.com"
FACILITY = "facility@example.com"

# (компания, задача, ответственный, цикл в днях, срок относительно сегодня, статус)
# Срок = None — задача ещё ни разу не выполнялась (last_done_at пустой).
DEMO_TASKS = [
    ("Acme", "Продлить SSL-сертификат", OPS, 90, -5, Task.Status.ACTIVE),
    ("Acme", "Проверить восстановление из бэкапа", OPS, 7, 0, Task.Status.ACTIVE),
    ("Acme", "Обновить зависимости", DEV, 30, 1, Task.Status.ACTIVE),
    ("Globex", "Поверка огнетушителей", FACILITY, 365, 3, Task.Status.ACTIVE),
    ("Globex", "Продлить домен", OPS, 365, 4, Task.Status.ACTIVE),
    ("Globex", "Заменить фильтры кондиционеров", FACILITY, 60, -1, Task.Status.ACTIVE),
    ("Initech", "Ротация логов", DEV, 30, 30, Task.Status.ACTIVE),
    ("Initech", "Проверить ИБП", FACILITY, 180, -2, Task.Status.PAUSED),
    ("Initech", "Аудит прав доступа", OPS, 90, None, Task.Status.ACTIVE),
    ("Initech", "Ротация паролей сервисных учёток", DEV, 60, 2, Task.Status.ACTIVE),
]


class Command(BaseCommand):
    help = "Создать демо-компании и задачи с разными сроками."

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localdate()
        companies = {}
        for name in sorted({row[0] for row in DEMO_TASKS}):
            company, _ = Company.objects.get_or_create(name=name)
            company.tasks.all().delete()
            companies[name] = company

        for company_name, title, email, cycle_days, due_in, status in DEMO_TASKS:
            # Подбираем last_done_at так, чтобы срок (last_done_at + cycle_days)
            # оказался ровно через due_in дней от сегодня.
            last_done_at = None if due_in is None else today + timedelta(days=due_in - cycle_days)
            task = Task.objects.create(
                company=companies[company_name],
                title=title,
                responsible_email=email,
                cycle_days=cycle_days,
                last_done_at=last_done_at,
                status=status,
            )
            self.stdout.write(f"  {task}: срок {task.next_due_date:%d.%m.%Y} ({status})")

        self.stdout.write(self.style.SUCCESS(f"Создано задач: {len(DEMO_TASKS)}"))
