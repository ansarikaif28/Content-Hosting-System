"""Django admin configuration for content models."""

import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.utils import timezone

from content.constants import STATUS_DELETED
from content.models import LiveState, UploadHistory


class PruneStatusFilter(admin.SimpleListFilter):
    """Filter uploads by their prune eligibility status."""

    title = 'prune status'
    parameter_name = 'prune_status'

    def lookups(self, request, model_admin):
        return [
            ('prunable', 'Ready to prune'),
            ('too_recent', 'Too recent'),
            ('dont_deleted', 'Dont deleted'),
        ]

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset

        archive_days = getattr(settings, 'PRUNE_ARCHIVE_DAYS', 180)
        cutoff = timezone.now() - timedelta(days=archive_days)

        active_hashes = set(
            LiveState.objects.values_list('current_hash', flat=True)
        )

        if self.value() == 'not_deleted':
            return queryset.exclude(status=STATUS_DELETED)

        deleted = queryset.filter(status=STATUS_DELETED)

        if self.value() == 'too_recent':
            return deleted.filter(updated_at__gte=cutoff)

        old_deleted = deleted.filter(updated_at__lt=cutoff)

        linked_pks = []
        prunable_pks = []

        for upload in old_deleted:
            archive_path = Path(settings.ARCHIVE_DIR) / upload.hash_value
            refs = _get_all_references(upload, archive_path, active_hashes)
            if refs:
                linked_pks.append(upload.pk)
            else:
                prunable_pks.append(upload.pk)

        if self.value() == 'linked':
            return queryset.filter(pk__in=linked_pks)

        if self.value() == 'prunable':
            return queryset.filter(pk__in=prunable_pks)

        return queryset


# ── Helper functions ─────────────────────────────────────────────────────

def _find_linked_folders(archive_path: Path) -> list[str]:
    """
    Scan deployment directories for hard links to files in this archive.
    Returns sorted list of folder/environment names.
    """
    if not archive_path.exists():
        return []

    archive_inodes = set()
    for f in archive_path.rglob('*'):
        if f.is_file():
            try:
                stat = os.stat(str(f))
                if stat.st_nlink > 1:
                    archive_inodes.add(stat.st_ino)
            except OSError:
                continue

    if not archive_inodes:
        return []

    live_dir = getattr(settings, 'LIVE_DIR', None)
    if not live_dir:
        return []

    live_path = Path(live_dir)
    if not live_path.exists():
        return []

    linked = set()
    for env_dir in live_path.iterdir():
        if not env_dir.is_dir():
            continue
        for f in env_dir.rglob('*'):
            if f.is_file():
                try:
                    if os.stat(str(f)).st_ino in archive_inodes:
                        linked.add(env_dir.name)
                        break
                except OSError:
                    continue

    return sorted(linked)


def _get_all_references(upload, archive_path: Path, active_hashes: set) -> list[str]:
    """
    Get all references from both database (LiveState) and filesystem
    (hard links). Returns sorted deduplicated list of names.
    """
    refs = set()

    live_envs = LiveState.objects.filter(
        current_hash=upload.hash_value
    ).values_list('environment', flat=True)
    refs.update(live_envs)

    fs_refs = _find_linked_folders(archive_path)
    refs.update(fs_refs)

    return sorted(refs)


def _format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 ** 3:
        return f'{size_bytes / (1024 ** 3):.2f} GB'
    if size_bytes >= 1024 ** 2:
        return f'{size_bytes / (1024 ** 2):.2f} MB'
    if size_bytes >= 1024:
        return f'{size_bytes / 1024:.2f} KB'
    return f'{size_bytes} bytes'


def _get_folder_size(folder: Path) -> int:
    if not folder.exists():
        return 0
    try:
        return sum(
            f.stat().st_size
            for f in folder.rglob('*')
            if f.is_file()
        )
    except (OSError, FileNotFoundError):
        return 0


# ── Admin classes ────────────────────────────────────────────────────────

@admin.register(UploadHistory)
class UploadHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'folder_name', 'hash_value_short', 'status',
        'uploaded_by', 'uploaded_at', 'linked_by', 'archive_size',
    ]
    list_filter = ['status', 'uploaded_at', PruneStatusFilter]
    search_fields = ['folder_name', 'hash_value', 'uploaded_by__username']
    readonly_fields = [
        'folder_name', 'hash_value', 'archive_path',
        'status', 'uploaded_by', 'uploaded_at', 'updated_at',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description='Hash')
    def hash_value_short(self, obj):
        return f"{obj.hash_value[:12]}..."

    @admin.display(description='Linked By')
    def linked_by(self, obj):
        archive_path = Path(settings.ARCHIVE_DIR) / obj.hash_value
        active_hashes = set(
            LiveState.objects.values_list('current_hash', flat=True)
        )
        refs = _get_all_references(obj, archive_path, active_hashes)
        if refs:
            return ', '.join(refs)
        return '\u2014'

    @admin.display(description='Size')
    def archive_size(self, obj):
        archive_path = Path(settings.ARCHIVE_DIR) / obj.hash_value
        size = _get_folder_size(archive_path)
        return _format_size(size)


@admin.register(LiveState)
class LiveStateAdmin(admin.ModelAdmin):
    list_display = [
        'environment', 'folder_name', 'current_hash_short',
        'updated_by', 'last_updated',
    ]
    list_filter = ['environment']
    search_fields = ['folder_name', 'current_hash']
    readonly_fields = [
        'environment', 'folder_name', 'current_hash',
        'updated_by', 'last_updated',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description='Hash')
    def current_hash_short(self, obj):
        return f"{obj.current_hash[:12]}..."