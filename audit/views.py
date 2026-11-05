"""
Views for the audit log interface and CSV export.

Provides a filterable, sortable view of all system actions
and the ability to export logs as CSV files.
"""

import csv
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from audit.models import ActionLog
from content.constants import ACTION_TYPE_CHOICES


@login_required
def action_log_list_view(request):
    """
    Display the system audit logs with filtering and sorting.

    Supports:
        - Filter by action_type (dropdown)
        - Filter by date range
        - Search by hash or actor username
        - Column sorting
    """
    logs = ActionLog.objects.select_related('actor').all()

    # --- Filters ---
    action_filter = request.GET.get('action_type', '')
    if action_filter:
        logs = logs.filter(action_type=action_filter)

    search_query = request.GET.get('q', '').strip()
    if search_query:
        logs = logs.filter(
            related_hash__icontains=search_query
        ) | logs.filter(
            actor__username__icontains=search_query
        )

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            logs = logs.filter(
                timestamp__gte=timezone.make_aware(from_date)
            )
        except ValueError:
            pass
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d')
            to_date = to_date.replace(hour=23, minute=59, second=59)
            logs = logs.filter(
                timestamp__lte=timezone.make_aware(to_date)
            )
        except ValueError:
            pass

    # --- Sorting ---
    sort_field = request.GET.get('sort', '-timestamp')
    allowed_sort_fields = [
        'timestamp', '-timestamp',
        'action_type', '-action_type',
        'related_hash', '-related_hash',
    ]
    if sort_field in allowed_sort_fields:
        logs = logs.order_by(sort_field)

    context = {
        'logs': logs[:500],  # Limit for performance
        'action_type_choices': ACTION_TYPE_CHOICES,
        'current_action_filter': action_filter,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'current_sort': sort_field,
    }

    template = 'audit/logs.html'
    if hasattr(request, 'htmx') and request.htmx:
        template = 'audit/partials/logs_table.html'

    return render(request, template, context)


@login_required
def export_logs_csv_view(request):
    """
    Export filtered audit logs as a CSV file download.

    Applies the same filters as the list view so the export
    matches what the user sees on screen.
    """
    logs = ActionLog.objects.select_related('actor').all()

    # Apply same filters as list view
    action_filter = request.GET.get('action_type', '')
    if action_filter:
        logs = logs.filter(action_type=action_filter)

    search_query = request.GET.get('q', '').strip()
    if search_query:
        logs = logs.filter(
            related_hash__icontains=search_query
        ) | logs.filter(
            actor__username__icontains=search_query
        )

    # Build CSV response
    timestamp_str = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f'audit_logs_{timestamp_str}.csv'

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        'Timestamp', 'Actor', 'Action', 'Entity Type',
        'Entity ID', 'Hash', 'Old State', 'New State',
        'Details', 'IP Address',
    ])

    for log in logs:
        writer.writerow([
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            log.actor.username if log.actor else 'System',
            log.action_type,
            log.entity_type,
            log.entity_id or '',
            log.related_hash,
            log.old_state or '',
            log.new_state or '',
            log.details or '',
            log.ip_address or '',
        ])

    return response