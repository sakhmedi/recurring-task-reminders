from __future__ import annotations

from datetime import date, timedelta

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from .querysets import TaskQuerySet


class Company(models.Model):
    name = models.CharField("название", max_length=200, unique=True)
    created_at = models.DateTimeField("создана", auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "компания"
        verbose_name_plural = "компании"

    def __str__(self) -> str:
        return self.name


class Task(models.Model):
    """Повторяющаяся задача: выполнять раз в ``cycle_days`` дней."""

    class Status(models.TextChoices):
        ACTIVE = "active", "активна"
        PAUSED = "paused", "на паузе"

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="tasks", verbose_name="компания"
    )
    title = models.CharField("название", max_length=255)
    responsible_email = models.EmailField("ответственный")
    cycle_days = models.PositiveIntegerField("цикл, дней", validators=[MinValueValidator(1)])
    # null = задача ещё ни разу не выполнялась.
    last_done_at = models.DateField("выполнена", null=True, blank=True)
    status = models.CharField(
        "статус", max_length=10, choices=Status.choices, default=Status.ACTIVE
    )
    created_at = models.DateTimeField("создана", auto_now_add=True)

    objects = TaskQuerySet.as_manager()

    class Meta:
        ordering = ["company__name", "title"]
        verbose_name = "задача"
        verbose_name_plural = "задачи"
        constraints = [
            # Валидатор работает только в формах, а это ограничение — на уровне БД.
            models.CheckConstraint(
                condition=models.Q(cycle_days__gte=1), name="task_cycle_days_gte_1"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.company} — {self.title}"

    @property
    def next_due_date(self) -> date:
        """Дата следующего выполнения.

        Если задача ещё ни разу не выполнялась, срок — день создания
        (по Алматы), то есть задача сразу считается «к выполнению».
        """
        if self.last_done_at is None:
            # localdate(None) = сегодня: удобно для ещё не сохранённой задачи.
            return timezone.localdate(self.created_at)
        return self.last_done_at + timedelta(days=self.cycle_days)

    def is_due(self, days_ahead: int = 0, today: date | None = None) -> bool:
        """True, если задача активна и срок наступает в ближайшие ``days_ahead`` дней
        (включительно) или уже прошёл."""
        if today is None:
            today = timezone.localdate()
        if self.status != self.Status.ACTIVE:
            return False
        return self.next_due_date <= today + timedelta(days=days_ahead)

    def mark_done(self, on: date | None = None) -> None:
        """Отметить выполненной: следующий срок сдвигается на ``cycle_days`` от ``on``."""
        self.last_done_at = on if on is not None else timezone.localdate()
        self.save(update_fields=["last_done_at"])


class ReminderLog(models.Model):
    """Журнал отправленных дайджестов. Не более одной записи на (email, день) —
    это и есть защита от повторной отправки."""

    email = models.EmailField()
    sent_on = models.DateField()
    task_ids = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_on", "email"]
        verbose_name = "отправленный дайджест"
        verbose_name_plural = "отправленные дайджесты"
        constraints = [
            models.UniqueConstraint(
                fields=["email", "sent_on"], name="unique_digest_per_email_day"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.email} @ {self.sent_on}"
