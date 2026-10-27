from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.utils.html import format_html

from .models import Company, ReminderLog, Task
from .services import due_label, due_state

# Цвет пометки для каждого состояния из services.due_state().
BADGE_COLORS = {
    "overdue": "#c62828",  # красный
    "soon": "#ef6c00",  # оранжевый
    "ok": "#2e7d32",  # зелёный
    "paused": "#757575",  # серый
}


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = ("title", "responsible_email", "cycle_days", "last_done_at", "status")
    show_change_link = True


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    inlines = [TaskInline]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "title",
        "responsible_email",
        "cycle_days",
        "last_done_at",
        "due_date",
        "due_badge",
        "status",
    )
    list_filter = ("status", "company")
    search_fields = ("title", "responsible_email", "company__name")
    list_select_related = ("company",)
    readonly_fields = ("next_due_date", "created_at")
    actions = ["mark_done"]
    # Свой шаблон только добавляет кнопку «Отметить выполненным» на страницу задачи.
    change_form_template = "admin/reminders/task/change_form.html"

    def get_queryset(self, request):
        # Аннотация next_due нужна, чтобы по сроку можно было сортировать в списке.
        return super().get_queryset(request).with_next_due()

    @admin.display(description="следующий срок", ordering="next_due")
    def due_date(self, obj: Task):
        return obj.next_due_date

    @admin.display(description="состояние")
    def due_badge(self, obj: Task):
        today = timezone.localdate()
        state = due_state(obj, today)
        text = "на паузе" if state == "paused" else due_label(obj.next_due_date, today)
        return format_html(
            '<span style="color:#fff;background:{};padding:2px 8px;border-radius:8px;'
            'white-space:nowrap">{}</span>',
            BADGE_COLORS[state],
            text,
        )

    @admin.action(description="Отметить выполненным (сегодня)")
    def mark_done(self, request, queryset):
        today = timezone.localdate()
        count = 0
        for task in queryset:
            task.mark_done(today)
            count += 1
        self.message_user(request, f"Отмечено выполненными: {count}", messages.SUCCESS)

    def response_change(self, request, obj):
        # Нажата кнопка «Отметить выполненным» на странице задачи.
        if "_mark_done" in request.POST:
            obj.mark_done()
            self.message_user(
                request,
                f"Задача выполнена. Следующий срок: {obj.next_due_date:%d.%m.%Y}",
                messages.SUCCESS,
            )
            return HttpResponseRedirect(request.path)
        return super().response_change(request, obj)


@admin.register(ReminderLog)
class ReminderLogAdmin(admin.ModelAdmin):
    list_display = ("sent_on", "email", "task_ids", "created_at")
    list_filter = ("sent_on",)
    search_fields = ("email",)
