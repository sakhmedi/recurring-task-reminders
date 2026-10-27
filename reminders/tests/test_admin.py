from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


def test_changelist_renders_with_badges(admin_client, make_task):
    make_task(-1, title="Просроченная")
    make_task(30, title="Нескоро")

    response = admin_client.get(reverse("admin:reminders_task_changelist"))

    assert response.status_code == 200
    html = response.content.decode()
    assert "Просроченная" in html
    assert "#c62828" in html  # красная пометка
    assert "#2e7d32" in html  # зелёная пометка


def test_changelist_sorts_by_next_due(admin_client, make_task):
    make_task(5, title="Позже")
    make_task(-5, title="Раньше")

    # Колонка «следующий срок» — 6-я в list_display; сортировка по ней идёт в БД.
    response = admin_client.get(reverse("admin:reminders_task_changelist") + "?o=6")

    html = response.content.decode()
    assert html.index("Раньше") < html.index("Позже")


def test_mark_done_action_updates_last_done_at(admin_client, make_task):
    today = timezone.localdate()
    task1 = make_task(-3, cycle_days=10)
    task2 = make_task(0, cycle_days=7)
    untouched = make_task(-1)
    untouched_before = untouched.last_done_at

    response = admin_client.post(
        reverse("admin:reminders_task_changelist"),
        {"action": "mark_done", "_selected_action": [task1.pk, task2.pk]},
        follow=True,
    )

    assert response.status_code == 200
    task1.refresh_from_db()
    task2.refresh_from_db()
    untouched.refresh_from_db()
    assert task1.last_done_at == today
    assert task1.next_due_date == today + timedelta(days=10)
    assert task2.next_due_date == today + timedelta(days=7)
    assert untouched.last_done_at == untouched_before
    assert "Отмечено выполненными: 2" in response.content.decode()


def test_mark_done_button_on_change_page(admin_client, make_task):
    task = make_task(-3, cycle_days=10)
    url = reverse("admin:reminders_task_change", args=[task.pk])

    page = admin_client.get(url)
    assert 'name="_mark_done"' in page.content.decode()

    response = admin_client.post(
        url,
        {
            "company": task.company_id,
            "title": task.title,
            "responsible_email": task.responsible_email,
            "cycle_days": task.cycle_days,
            "last_done_at": task.last_done_at.isoformat(),
            "status": task.status,
            "_mark_done": "1",
        },
    )

    assert response.status_code == 302
    task.refresh_from_db()
    assert task.last_done_at == timezone.localdate()


def test_company_page_has_task_inline(admin_client, make_task):
    task = make_task(0, title="Inline-задача")
    response = admin_client.get(reverse("admin:reminders_company_change", args=[task.company_id]))
    assert "Inline-задача" in response.content.decode()
