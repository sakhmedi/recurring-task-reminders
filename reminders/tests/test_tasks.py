from datetime import timedelta
from unittest import mock

import pytest
from django.core import mail

from reminders.models import Company, ReminderLog, Task
from reminders.services import due_label
from reminders.tasks import send_due_digests

from .conftest import TODAY, almaty

pytestmark = pytest.mark.django_db

OPS = "ops@example.com"
DEV = "dev@example.com"


@pytest.fixture(autouse=True)
def frozen_today(time_machine):
    """Во всех тестах рассылки «сейчас» = TODAY, 09:00 по Алматы (как у beat)."""
    time_machine.move_to(almaty(TODAY, hour=9), tick=False)
    return time_machine


def test_one_digest_per_responsible(make_task):
    make_task(-1, email=OPS, title="SSL")
    make_task(0, email=OPS, title="Бэкап")
    make_task(3, email=OPS, title="Домен")
    make_task(1, email=DEV, title="Зависимости")

    assert send_due_digests(days_ahead=3) == 2
    assert len(mail.outbox) == 2

    by_recipient = {m.to[0]: m for m in mail.outbox}
    ops_body = by_recipient[OPS].body
    for title in ("SSL", "Бэкап", "Домен"):
        assert title in ops_body
    assert "Зависимости" not in ops_body
    assert "Зависимости" in by_recipient[DEV].body


def test_digest_is_sorted_and_labelled(make_task):
    make_task(3, title="Третья")
    make_task(-2, title="Просроченная")
    make_task(0, title="Сегодняшняя")

    send_due_digests(days_ahead=3)
    body = mail.outbox[0].body

    assert body.index("Просроченная") < body.index("Сегодняшняя") < body.index("Третья")
    assert "ПРОСРОЧЕНО на 2 дн." in body
    assert "сегодня" in body
    assert "через 3 дн." in body
    assert "Acme" in body  # компания тоже указана


def test_tasks_outside_window_and_paused_are_skipped(make_task):
    make_task(0, title="В окне")
    make_task(4, title="За окном")
    make_task(-5, title="На паузе", status=Task.Status.PAUSED)
    make_task(0, email=DEV, title="Только пауза", status=Task.Status.PAUSED)

    assert send_due_digests(days_ahead=3) == 1
    body = mail.outbox[0].body
    assert "В окне" in body
    assert "За окном" not in body
    assert "На паузе" not in body
    assert mail.outbox[0].to == [OPS]


def test_no_due_tasks_no_emails(make_task):
    make_task(10)
    assert send_due_digests(days_ahead=3) == 0
    assert mail.outbox == []


def test_second_run_same_day_sends_nothing(make_task):
    make_task(0, email=OPS)
    make_task(0, email=DEV)

    assert send_due_digests(days_ahead=3) == 2
    assert send_due_digests(days_ahead=3) == 0
    assert len(mail.outbox) == 2
    assert ReminderLog.objects.count() == 2


def test_next_day_sends_again(make_task, frozen_today):
    task = make_task(0)
    assert send_due_digests(days_ahead=3) == 1

    frozen_today.shift(timedelta(days=1))
    assert send_due_digests(days_ahead=3) == 1
    assert len(mail.outbox) == 2
    assert "ПРОСРОЧЕНО на 1 дн." in mail.outbox[1].body

    log_days = set(ReminderLog.objects.values_list("sent_on", flat=True))
    assert log_days == {TODAY, TODAY + timedelta(days=1)}
    assert ReminderLog.objects.get(sent_on=TODAY).task_ids == [task.pk]


def test_done_task_disappears_from_digest(make_task, frozen_today):
    done = make_task(0, title="Уже сделали")
    make_task(1, title="Ещё нет")

    done.mark_done()
    send_due_digests(days_ahead=3)

    body = mail.outbox[0].body
    assert "Уже сделали" not in body
    assert "Ещё нет" in body


def test_failed_send_does_not_block_retry(make_task):
    """Если отправка упала, запись в журнале откатывается и повтор отправит письмо."""
    make_task(0)

    with mock.patch("reminders.services.send_mail", side_effect=ConnectionError("smtp down")):
        with pytest.raises(ConnectionError):
            send_due_digests(days_ahead=3)
    assert ReminderLog.objects.count() == 0

    assert send_due_digests(days_ahead=3) == 1


def test_already_logged_email_is_skipped(make_task):
    """Запись в журнале, созданная «другим воркером», блокирует отправку."""
    make_task(0, email=OPS)
    make_task(0, email=DEV)
    ReminderLog.objects.create(email=OPS, sent_on=TODAY)

    assert send_due_digests(days_ahead=3) == 1
    assert mail.outbox[0].to == [DEV]


def test_tasks_of_different_companies_in_one_digest(make_task):
    other = Company.objects.create(name="Globex")
    make_task(0, title="Acme-задача")
    make_task(1, title="Globex-задача", company_obj=other)

    assert send_due_digests(days_ahead=3) == 1
    body = mail.outbox[0].body
    assert "[Acme] Acme-задача" in body
    assert "[Globex] Globex-задача" in body


@pytest.mark.parametrize(
    ("days_left", "label"),
    [(-3, "ПРОСРОЧЕНО на 3 дн."), (0, "сегодня"), (1, "через 1 дн."), (3, "через 3 дн.")],
)
def test_due_label(days_left, label):
    assert due_label(TODAY + timedelta(days=days_left), TODAY) == label
