import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db

UPCOMING = reverse("reminders:upcoming")
HTMX = {"HTTP_HX_REQUEST": "true"}


def test_requires_login(client):
    response = client.get(UPCOMING)
    assert response.status_code == 302
    assert reverse("admin:login") in response["Location"]


def test_requires_staff(client):
    user = get_user_model().objects.create_user("bob", password="pass")
    client.force_login(user)
    assert client.get(UPCOMING).status_code == 302


def test_mark_done_requires_staff(client, make_task):
    task = make_task(0)
    response = client.post(reverse("reminders:mark_done", args=[task.pk]))
    assert response.status_code == 302
    task.refresh_from_db()
    assert task.last_done_at != timezone.localdate()


def test_full_page(admin_client, make_task):
    make_task(0, title="Сегодняшняя")
    response = admin_client.get(UPCOMING)

    html = response.content.decode()
    assert response.status_code == 200
    assert "<html" in html
    assert "htmx.org" in html
    assert "Сегодняшняя" in html


def test_htmx_request_returns_rows_fragment(admin_client, make_task):
    make_task(0, title="Сегодняшняя")
    response = admin_client.get(UPCOMING, **HTMX)

    html = response.content.decode()
    assert response.status_code == 200
    assert "<html" not in html
    assert "<tr" in html
    assert "Сегодняшняя" in html


@pytest.mark.parametrize(("days", "visible"), [(3, False), (7, True), (30, True)])
def test_days_filter(admin_client, make_task, days, visible):
    make_task(5, title="Через пять дней")
    html = admin_client.get(UPCOMING, {"days": days}, **HTMX).content.decode()
    assert ("Через пять дней" in html) is visible


def test_invalid_days_falls_back_to_default(admin_client, make_task):
    make_task(5, title="Через пять дней")  # видно при окне по умолчанию (7)
    html = admin_client.get(UPCOMING, {"days": "abc"}, **HTMX).content.decode()
    assert "Через пять дней" in html


def test_mark_done_returns_updated_row(admin_client, make_task):
    task = make_task(-2, cycle_days=14, title="Отметь меня")

    response = admin_client.post(reverse("reminders:mark_done", args=[task.pk]), **HTMX)

    html = response.content.decode()
    assert response.status_code == 200
    assert f'id="task-{task.pk}"' in html
    assert "выполнено" in html
    assert "через 14 дн." in html
    task.refresh_from_db()
    assert task.last_done_at == timezone.localdate()


def test_mark_done_rejects_get(admin_client, make_task):
    task = make_task(0)
    assert admin_client.get(reverse("reminders:mark_done", args=[task.pk])).status_code == 405
