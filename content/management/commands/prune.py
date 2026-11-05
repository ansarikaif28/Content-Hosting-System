"""
Management command for safe cleanup of historical data.

Removes old ActionLog entries and pruned archive folders based on
configurable age thresholds AND hard link reference counts.
Never deletes data that is actively referenced by a LiveState deployment.

Usage:
    python manage.py prune                    # Use defaults from .env
    python manage.py prune --log-days 180     # Override log retention
    python manage.py prune --dry-run          # Preview what would be deleted
"""

import os
import shutil
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from audit.models import ActionLog
from content.constants import STATUS_DELETED
from content.models import LiveState, UploadHistory


class Command(BaseCommand):
    help = (
        'Safely prune old audit logs and deleted archive folders. '
        'Never removes data referenced by active deployments or hard links.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--log-days',
            type=int,
            default=settings.PRUNE_LOG_DAYS,
            help=f'Delete log entries older than N days '
                 f'(default: {settings.PRUNE_LOG_DAYS})',
        )
        parser.add_argument(
            '--archive-days',
            type=int,
            default=settings.PRUNE_ARCHIVE_DAYS,
            help=f'Delete archived folders older than N days '
                 f'(default: {settings.PRUNE_ARCHIVE_DAYS})',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting.',
        )

    def handle(self, *args, **options):
        log_days = options['log_days']
        archive_days = options['archive_days']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('=== DRY RUN MODE ==='))

        log_count = self._prune_old_logs(log_days, dry_run)
        archive_count = self._prune_old_archives(archive_days, dry_run)

        self.stdout.write(self.style.SUCCESS(
            f'\nPrune complete: '
            f'{log_count} log entries, '
            f'{archive_count} archive folders '
            f'{"would be " if dry_run else ""}deleted.'
        ))

    def _prune_old_logs(self, days: int, dry_run: bool) -> int:
        """Delete ActionLog entries older than the specified number of days."""
        cutoff = timezone.now() - timedelta(days=days)
        old_logs = ActionLog.objects.filter(timestamp__lt=cutoff)
        count = old_logs.count()

        self.stdout.write(
            f'Found {count} log entries older than {days} days.'
        )

        if not dry_run and count > 0:
            old_logs.delete()
            self.stdout.write(
                self.style.SUCCESS(f'  Deleted {count} log entries.')
            )

        return count

    def _has_hard_links(self, path: Path) -> bool:
        """
        Check if a path has any hard links pointing to it.
        Returns True if hard link count > 1, False otherwise.
        """
        try:
            stat_info = os.stat(str(path))
            # st_nlink is the number of hard links
            return stat_info.st_nlink > 1
        except (OSError, FileNotFoundError):
            # If path doesn't exist or can't be accessed, treat as no hard links
            return False

    def _is_prunable(self, upload: UploadHistory, active_hashes: set, 
                     days_threshold: int) -> tuple[bool, str]:
        """
        Determine if an upload is prunable based on:
        1. Not actively deployed (not in active_hashes)
        2. Old enough (past days threshold)
        3. No hard links pointing to the archive folder

        Returns: (is_prunable: bool, reason: str)
        """
        archive_path = Path(settings.ARCHIVE_DIR) / upload.hash_value

        # Check 1: Is it actively deployed?
        if upload.hash_value in active_hashes:
            return False, f'still has active deployment'

        # Check 2: Is it old enough?
        cutoff = timezone.now() - timedelta(days=days_threshold)
        if upload.updated_at >= cutoff:
            return False, f'not old enough (updated {upload.updated_at})'

        # Check 3: Does it have hard links?
        if not archive_path.exists():
            # Path doesn't exist, safe to prune the database record
            return True, 'archive path does not exist'

        if self._has_hard_links(archive_path):
            link_count = os.stat(str(archive_path)).st_nlink
            return False, f'has {link_count} hard link(s)'

        # All checks passed
        return True, 'meets all pruning criteria'

    def _prune_old_archives(self, days: int, dry_run: bool) -> int:
        """
        Delete archive folders for uploads that were deleted more than
        N days ago, have no active LiveState references, AND have no
        hard links pointing to them.
        """
        # Find all deleted uploads
        deleted_uploads = UploadHistory.objects.filter(
            status=STATUS_DELETED,
        )

        # Get hashes that are actively deployed (NEVER delete these)
        active_hashes = set(
            LiveState.objects.values_list('current_hash', flat=True)
        )

        pruned_count = 0
        skipped_count = 0

        for upload in deleted_uploads:
            is_prunable, reason = self._is_prunable(
                upload, 
                active_hashes, 
                days
            )

            if not is_prunable:
                self.stdout.write(
                    self.style.WARNING(
                        f'  SKIPPED {upload.hash_value[:12]}... '
                        f'({reason})'
                    )
                )
                skipped_count += 1
                continue

            archive_path = Path(settings.ARCHIVE_DIR) / upload.hash_value

            self.stdout.write(
                f'  Pruning archive: {upload.folder_name} '
                f'({upload.hash_value[:12]}...) - {reason}'
            )

            if not dry_run:
                # Delete the archive folder if it exists
                if archive_path.exists():
                    try:
                        shutil.rmtree(str(archive_path))
                    except OSError as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f'    ERROR: Failed to delete folder: {e}'
                            )
                        )
                        continue

                # Delete the database record
                try:
                    upload.delete()
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'    ERROR: Failed to delete record: {e}'
                        )
                    )
                    continue

            pruned_count += 1

        if skipped_count > 0:
            self.stdout.write(
                f'\nSkipped {skipped_count} archives '
                f'(active deployments or hard links)'
            )

        return pruned_count