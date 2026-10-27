from celery import shared_task

from . import services


@shared_task
def send_due_digests(days_ahead: int = 3) -> int:
    """Ежедневная рассылка (запускается celery beat в 09:00 по Алматы).

    Возвращает число отправленных писем. В тестах вызываем напрямую:
    ``send_due_digests(days_ahead=3)`` — это обычный синхронный вызов функции.
    """
    return services.send_due_digests(days_ahead=days_ahead)
