"""Запросы к задачам, которые выполняются целиком в БД (без перебора в Python)."""

from __future__ import annotations

from datetime import date, timedelta

from django.db import models
from django.db.models import DateField, ExpressionWrapper, F
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone


class TaskQuerySet(models.QuerySet):
    def active(self) -> TaskQuerySet:
        return self.filter(status=self.model.Status.ACTIVE)

    def with_next_due(self) -> TaskQuerySet:
        """Добавляет к каждой задаче поле ``next_due`` — то же, что ``Task.next_due_date``.

        SQL (PostgreSQL):
            COALESCE(last_done_at + cycle_days, (created_at AT TIME ZONE 'Asia/Almaty')::date)

        * В PostgreSQL ``date + integer`` даёт ``date`` (прибавляет дни), поэтому
          29 февраля и переходы через конец месяца БД считает сама.
        * ``TruncDate`` берёт дату в текущем часовом поясе Django (TIME_ZONE),
          так же как ``timezone.localdate()`` в Python-версии.
        """
        return self.annotate(
            next_due=Coalesce(
                ExpressionWrapper(F("last_done_at") + F("cycle_days"), output_field=DateField()),
                TruncDate("created_at"),
                output_field=DateField(),
            )
        )

    def due(self, days_ahead: int = 0, today: date | None = None) -> TaskQuerySet:
        """Активные задачи со сроком не позже ``today + days_ahead`` (просроченные тоже).

        Результат совпадает с ``[t for t in Task.objects.all() if t.is_due(days_ahead, today)]``,
        это проверяет тест. Отсортировано по сроку.
        """
        if today is None:
            today = timezone.localdate()
        deadline = today + timedelta(days=days_ahead)
        return (
            self.active().with_next_due().filter(next_due__lte=deadline).order_by("next_due", "pk")
        )
