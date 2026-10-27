from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from reminders.models import Task

from .conftest import TODAY, almaty

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("due_in", "days_ahead", "expected"),
    [
        (0, 0, True),  # срок сегодня
        (0, 3, True),
        (3, 3, True),  # граница окна включительно
        (3, 2, False),
        (4, 3, False),  # на день за границей окна
        (1, 0, False),  # завтра при окне 0
        (-1, 0, True),  # просрочено на день
        (-100, 3, True),  # давно просрочено
    ],
)
def test_is_due_boundaries(make_task, due_in, days_ahead, expected):
    task = make_task(due_in)
    assert task.next_due_date == TODAY + timedelta(days=due_in)
    assert task.is_due(days_ahead=days_ahead, today=TODAY) is expected


def test_paused_task_is_never_due(make_task):
    task = make_task(-10, status=Task.Status.PAUSED)
    assert task.is_due(days_ahead=3, today=TODAY) is False


def test_never_done_task_is_due_from_creation_day(make_task, time_machine):
    # Создаём задачу 10 июня в 02:00 по Алматы — в UTC это ещё 9 июня.
    # Срок должен считаться по локальной дате, т.е. 10 июня.
    time_machine.move_to(almaty(TODAY, hour=2), tick=False)
    task = make_task(None)

    assert task.last_done_at is None
    assert task.next_due_date == TODAY
    assert task.is_due(today=TODAY) is True
    assert task.is_due(today=TODAY - timedelta(days=1)) is False
    # Через месяц всё ещё «к выполнению» (просрочена), пока не отметят.
    assert task.is_due(today=TODAY + timedelta(days=30)) is True


def test_mark_done_shifts_due_date_by_cycle(make_task):
    task = make_task(-5, cycle_days=90)
    task.mark_done(on=TODAY)
    task.refresh_from_db()

    assert task.last_done_at == TODAY
    assert task.next_due_date == TODAY + timedelta(days=90)
    assert task.is_due(days_ahead=3, today=TODAY) is False


def test_mark_done_defaults_to_local_today(make_task, time_machine):
    # 00:00 по Алматы 11 июня = 18:00 UTC 10 июня. Должна записаться локальная дата — 11-е.
    time_machine.move_to(almaty(TODAY + timedelta(days=1), hour=0), tick=False)
    task = make_task(0)
    task.mark_done()
    assert task.last_done_at == TODAY + timedelta(days=1)


@pytest.mark.parametrize(
    ("last_done_at", "cycle_days", "expected"),
    [
        (date(2028, 2, 28), 1, date(2028, 2, 29)),  # високосный год
        (date(2028, 2, 28), 2, date(2028, 3, 1)),
        (date(2027, 2, 28), 1, date(2027, 3, 1)),  # невисокосный
        (date(2028, 2, 29), 365, date(2029, 2, 28)),
        (date(2028, 1, 31), 30, date(2028, 3, 1)),  # через конец месяца
        (date(2026, 4, 30), 1, date(2026, 5, 1)),
        (date(2026, 12, 31), 1, date(2027, 1, 1)),  # через конец года
    ],
)
def test_next_due_date_calendar_edges(make_task, last_done_at, cycle_days, expected):
    task = make_task(last_done_at=last_done_at, cycle_days=cycle_days)
    assert task.next_due_date == expected
    # БД должна посчитать так же.
    assert Task.objects.with_next_due().get(pk=task.pk).next_due == expected


def test_is_due_across_month_end_in_leap_year(make_task):
    task = make_task(last_done_at=date(2028, 2, 27), cycle_days=3)  # срок 1 марта
    today = date(2028, 2, 27)
    assert task.is_due(days_ahead=3, today=today) is True
    assert task.is_due(days_ahead=2, today=today) is False  # 27 + 2 = 29 февраля


def test_cycle_days_must_be_positive(make_task):
    task = make_task(0)
    task.cycle_days = 0
    with pytest.raises(ValidationError):
        task.full_clean()
    with pytest.raises(IntegrityError):
        task.save()


@pytest.mark.parametrize("days_ahead", [0, 1, 2, 3, 4, 30])
@pytest.mark.parametrize("today", [TODAY, date(2028, 2, 27), date(2026, 12, 30)])
def test_queryset_due_matches_is_due(make_task, time_machine, days_ahead, today):
    """Фильтр в БД и Python-метод должны выбирать одни и те же задачи."""
    time_machine.move_to(almaty(TODAY), tick=False)
    for due_in in (-30, -1, 0, 1, 2, 3, 4, 5, 30, 31):
        make_task(due_in)
        make_task(due_in, status=Task.Status.PAUSED)
    make_task(None)  # без last_done_at
    make_task(last_done_at=date(2028, 2, 26), cycle_days=3)  # 29 февраля
    make_task(last_done_at=date(2026, 12, 1), cycle_days=31)  # 1 января

    expected = sorted(t.pk for t in Task.objects.all() if t.is_due(days_ahead, today))
    actual = sorted(Task.objects.due(days_ahead, today).values_list("pk", flat=True))
    assert actual == expected
    assert actual  # набор не пустой — иначе тест ничего не проверяет


def test_queryset_due_is_sorted_by_due_date(make_task):
    t3 = make_task(3)
    t_overdue = make_task(-2)
    t0 = make_task(0)
    assert list(Task.objects.due(3, TODAY)) == [t_overdue, t0, t3]
