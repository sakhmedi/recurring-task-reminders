from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from reminders.models import Company, Task

ALMATY = ZoneInfo("Asia/Almaty")
# Фиксированное «сегодня» для всех тестов.
TODAY = date(2026, 6, 10)


def almaty(d: date, hour: int = 10) -> datetime:
    """Момент времени в указанный день по Алматы (для time_machine)."""
    return datetime(d.year, d.month, d.day, hour, tzinfo=ALMATY)


@pytest.fixture(autouse=True)
def freeze_time(time_machine):
    """Во всех тестах «сейчас» = TODAY 10:00 по Алматы, чтобы результат не зависел
    от дня запуска. Отдельные тесты могут переставить время через time_machine.move_to()."""
    time_machine.move_to(almaty(TODAY), tick=False)
    return time_machine


@pytest.fixture
def company(db):
    return Company.objects.create(name="Acme")


@pytest.fixture
def make_task(db, company):
    """Фабрика задач. ``due_in`` — через сколько дней от TODAY срок (можно отрицательный)."""

    def _make(
        due_in: int | None = 0,
        *,
        cycle_days: int = 30,
        email: str = "ops@example.com",
        status: str = Task.Status.ACTIVE,
        title: str = "Задача",
        company_obj: Company | None = None,
        last_done_at: date | None = None,
    ) -> Task:
        if last_done_at is None and due_in is not None:
            last_done_at = TODAY + timedelta(days=due_in - cycle_days)
        return Task.objects.create(
            company=company_obj or company,
            title=title,
            responsible_email=email,
            cycle_days=cycle_days,
            last_done_at=last_done_at,
            status=status,
        )

    return _make
