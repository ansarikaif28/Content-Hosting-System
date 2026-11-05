"""Django admin configuration for the CustomUser model."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from users.models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Admin interface for managing users and their roles."""

    list_display = ['username', 'email', 'role']
    list_filter = ['role']
    search_fields = ['username', 'email']

    # Add the role field to the admin form
    fieldsets = UserAdmin.fieldsets + (
        ('Role Assignment', {
            'fields': ('role',),
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role Assignment', {
            'fields': ('role',),
        }),
    )