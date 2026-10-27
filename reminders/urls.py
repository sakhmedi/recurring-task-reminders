from django.urls import path

from . import views

app_name = "reminders"

urlpatterns = [
    path("", views.upcoming, name="upcoming"),
    path("<int:pk>/done/", views.mark_done, name="mark_done"),
]
