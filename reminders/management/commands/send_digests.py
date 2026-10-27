from django.core.management.base import BaseCommand

from reminders.tasks import send_due_digests


class Command(BaseCommand):
    help = "Разослать дайджесты прямо сейчас (то же, что делает celery beat в 09:00)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days-ahead", type=int, default=3, help="окно в днях (по умолчанию 3)"
        )
        parser.add_argument(
            "--async",
            action="store_true",
            dest="use_celery",
            help="не выполнять здесь, а поставить задачу в очередь Celery "
            "(письма появятся в логах сервиса celery)",
        )

    def handle(self, *args, days_ahead: int, use_celery: bool, **options):
        if use_celery:
            result = send_due_digests.delay(days_ahead=days_ahead)
            self.stdout.write(f"Задача отправлена в Celery: {result.id}")
            return
        # Синхронный вызов: письма печатаются в stdout этого процесса.
        sent = send_due_digests(days_ahead=days_ahead)
        self.stdout.write(self.style.SUCCESS(f"Отправлено писем: {sent}"))
