"""Страница «Ближайшие сроки» на HTMX.

* GET /upcoming/?days=7 — вся страница; с заголовком HX-Request — только строки таблицы.
* POST /upcoming/<pk>/done/ — отметить выполненной, в ответ отдаём обновлённую строку.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import Task
from .services import due_label, due_state

DAY_CHOICES = (3, 7, 30)
DEFAULT_DAYS = 7


def _parse_days(request) -> int:
    """Берём ?days= из запроса; всё, кроме 3/7/30, заменяем на значение по умолчанию."""
    try:
        days = int(request.GET.get("days", DEFAULT_DAYS))
    except ValueError:
        return DEFAULT_DAYS
    return days if days in DAY_CHOICES else DEFAULT_DAYS


def _row(task: Task, today) -> dict:
    """Всё, что нужно шаблону строки таблицы."""
    return {
        "task": task,
        "due_date": task.next_due_date,
        "label": due_label(task.next_due_date, today),
        "state": due_state(task, today),
    }


@staff_member_required
@require_GET
def upcoming(request):
    today = timezone.localdate()
    days = _parse_days(request)
    tasks = Task.objects.due(days, today).select_related("company")
    context = {
        "rows": [_row(task, today) for task in tasks],
        "days": days,
        "day_choices": DAY_CHOICES,
        "today": today,
    }
    # HTMX присылает заголовок HX-Request — тогда отдаём только фрагмент с <tr>.
    template = (
        "reminders/_rows.html" if request.headers.get("HX-Request") else "reminders/upcoming.html"
    )
    return render(request, template, context)


@staff_member_required
@require_POST
def mark_done(request, pk: int):
    task = get_object_or_404(Task.objects.select_related("company"), pk=pk)
    task.mark_done()
    today = timezone.localdate()
    return render(request, "reminders/_row.html", {"row": _row(task, today), "just_done": True})
