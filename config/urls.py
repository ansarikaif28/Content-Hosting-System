"""
Root URL configuration for the Content Hosting System.

Routes are split across the three apps:
  - users:   authentication (login, logout, password reset)
  - content: uploads, dashboards
  - audit:   action logs, CSV export
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Root URL → redirect to dashboard (which redirects to login if needed)
    path('', RedirectView.as_view(url='/dashboard/', permanent=False), name='home'),

    path('', include('users.urls')),
    path('', include('content.urls')),
    path('', include('audit.urls')),
]


