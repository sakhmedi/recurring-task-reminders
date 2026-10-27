"""Бизнес-логика рассылки дайджестов.

Celery-задача и management-команда только вызывают ``send_due_digests`` отсюда,
поэтому логику легко тестировать без Celery.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import ReminderLog, Task

logger = logging.getLogger(__name__)

# Сколько дней до срока считается «скоро» (оранжевая пометка в admin и на /upcoming/).
SOON_DAYS = 3


def due_label(due_date: date, today: date) -> str:
    """Человекочитаемая пометка: «ПРОСРОЧЕНО на N дн.» / «сегодня» / «через N дн.»."""
    days_left = (due_date - today).days
    if days_left < 0:
        return f"ПРОСРОЧЕНО на {-days_left} дн."
    if days_left == 0:
        return "сегодня"
    return f"через {days_left} дн."


def due_state(task: Task, today: date) -> str:
    """Состояние для цветной пометки: overdue / soon / ok / paused."""
    if task.status != Task.Status.ACTIVE:
        return "paused"
    days_left = (task.next_due_date - today).days
    if days_left < 0:
        return "overdue"
    if days_left <= SOON_DAYS:
        return "soon"
    return "ok"


@dataclass
class DigestLine:
    """Одна строка в письме."""

    company: str
    title: str
    due_date: date
    label: str


def collect_digests(days_ahead: int, today: date) -> dict[str, list[Task]]:
    """Задачи к выполнению, сгруппированные по email ответственного.

    Один SQL-запрос; порядок задач внутри группы — по сроку (его задаёт ``due()``).
    """
    digests: dict[str, list[Task]] = defaultdict(list)
    for task in Task.objects.due(days_ahead, today).select_related("company"):
        digests[task.responsible_email].append(task)
    return dict(digests)


def send_digest(email: str, tasks: list[Task], today: date) -> bool:
    """Отправить одно письмо-дайджест, если сегодня этому адресу ещё не отправляли.

    Возвращает True, если письмо отправлено.

    Как защищаемся от дублей:
    1. В транзакции пытаемся создать ReminderLog(email, sent_on=today).
       На эту пару стоит UniqueConstraint, поэтому в БД может быть только одна такая запись.
    2. Если запись уже была (повторный запуск или параллельный воркер успел первым) —
       get_or_create вернёт created=False, и письмо не отправляем.
    3. Если send_mail упадёт, исключение откатит транзакцию вместе с записью в журнале,
       и следующий запуск попробует отправить ещё раз.
    """
    with transaction.atomic():
        _, created = ReminderLog.objects.get_or_create(
            email=email,
            sent_on=today,
            defaults={"task_ids": [task.pk for task in tasks]},
        )
        if not created:
            logger.info("Дайджест для %s за %s уже отправлен — пропускаем", email, today)
            return False

        lines = [
            DigestLine(
                company=task.company.name,
                title=task.title,
                due_date=task.next_due_date,
                label=due_label(task.next_due_date, today),
            )
            for task in tasks
        ]
        body = render_to_string(
            "reminders/email/digest.txt", {"email": email, "today": today, "lines": lines}
        )
        subject = f"Регламентные задачи на {today:%d.%m.%Y}: {len(lines)} шт."
        send_mail(subject, body, from_email=None, recipient_list=[email])

    logger.info("Дайджест отправлен: %s, задач: %d", email, len(tasks))
    return True


def send_due_digests(days_ahead: int = 3, today: date | None = None) -> int:
    """Разослать дайджесты всем ответственным. Возвращает число отправленных писем."""
    if today is None:
        today = timezone.localdate()
    sent = 0
    for email, tasks in collect_digests(days_ahead, today).items():
        if send_digest(email, tasks, today):
            sent += 1
    logger.info("Рассылка за %s (окно %d дн.): отправлено писем: %d", today, days_ahead, sent)
    return sent
