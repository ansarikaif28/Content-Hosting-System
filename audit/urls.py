"""URL routing for audit views."""

from django.urls import path
from audit import views

urlpatterns = [
    path('logs/', views.action_log_list_view, name='logs'),
    path('logs/export/', views.export_logs_csv_view, name='export_logs'),
]