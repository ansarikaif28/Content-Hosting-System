"""Read-only Django admin configuration for action logs."""

from django.contrib import admin
from audit.models import ActionLog


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    """Read-only admin interface for viewing audit logs."""

    list_display = [
        'timestamp', 'actor', 'action_type',
        'related_hash_short', 'ip_address',
    ]
    list_filter = ['action_type', 'timestamp', 'entity_type']
    search_fields = ['related_hash', 'actor__username']
    readonly_fields = [
        'actor', 'action_type', 'entity_type', 'entity_id',
        'related_hash', 'old_state', 'new_state', 'details',
        'timestamp', 'ip_address',
    ]
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Hash')
    def related_hash_short(self, obj):
        return f"{obj.related_hash[:12]}..." if obj.related_hash else '—'