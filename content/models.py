"""
Core data models for the content hosting system.

UploadHistory — immutable record of every upload.
LiveState     — Working state controller for test/production deployments.
"""

from django.conf import settings
from django.db import models

from content.constants import (
    STATUS_CHOICES, STATUS_PENDING,
    ENVIRONMENT_CHOICES, ENV_TEST,
)

# Supported language directories — extend this list for new languages
SUPPORTED_LANGUAGES = [
    ('en', 'English'),
    ('de', 'Deutsch'),
]


class UploadHistory(models.Model):
    """
    Permanent record of every content upload.

    Every file ever uploaded is tracked here. Even deleted uploads
    retain their record for audit and restoration purposes.
    The archive files can be pruned independently without affecting
    working deployments (thanks to hard links).
    """

    folder_name = models.CharField(
        max_length=255,
        help_text='Appropriate name for this content package.'
    )
    hash_value = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text='SHA-256 hash uniquely identifying this content.'
    )
    archive_path = models.CharField(
        max_length=500,
        help_text='Filesystem path to the archived content.'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
        help_text='Current workflow status of this upload.'
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploads',
        help_text='The user who uploaded this content.'
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='deleted_uploads',
        help_text='Who deleted this upload (for restore permission logic).'
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When this upload was deleted.'
    )
    replaces = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='replaced_by',
        help_text='The upload this one supersedes (re-upload chain).'
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When this content was first uploaded.'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text='When this record was last modified.'
    )
    file_count = models.PositiveIntegerField(
        default=0,
        help_text='Total number of files in this upload.'
    )
    total_size = models.PositiveIntegerField(
        default=0,
        help_text='Total size of all files in bytes.'
    )

    class Meta:
        verbose_name = 'Upload'
        verbose_name_plural = 'Upload History'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.folder_name} ({self.hash_value[:8]}...)"

    def get_test_url(self, language: str = 'en') -> str:
        """
        Return the test preview URL for a specific language.

        Args:
            language: Language code matching a subdirectory (e.g. 'en', 'de').

        Returns:
            URL string like /test/<hash>/en/index.html
        """
        return f"/test/{self.hash_value}/{language}/index.html"

    def get_production_url(self, language: str = 'en') -> str:
        """
        Return the production URL for a specific language.

        Args:
            language: Language code matching a subdirectory (e.g. 'en', 'de').

        Returns:
            URL string like /production/<hash>/en/index.html
        """
        return f"/production/{self.hash_value}/{language}/index.html"

    def get_all_test_urls(self) -> list[dict]:
        """
        Return test preview URLs for ALL supported languages.

        Returns:
            List of dicts: [{'code': 'en', 'label': 'English', 'url': '...'}, ...]
        """
        return [
            {
                'code': code,
                'label': label,
                'url': self.get_test_url(code),
            }
            for code, label in SUPPORTED_LANGUAGES
        ]

    def get_all_production_urls(self) -> list[dict]:
        """
        Return production URLs for ALL supported languages.

        Returns:
            List of dicts: [{'code': 'en', 'label': 'English', 'url': '...'}, ...]
        """
        return [
            {
                'code': code,
                'label': label,
                'url': self.get_production_url(code),
            }
            for code, label in SUPPORTED_LANGUAGES
        ]

    def get_total_size_display(self) -> str:
        """Return a human-readable file size string."""
        size = self.total_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def get_latest_action_reason(self) -> dict | None:
        """
        Get the reason and actor from the most recent reject/unpublish action.

        Queries the ActionLog for the latest REJECTED or UNPUBLISHED action
        on this upload and returns the reason and who performed it.

        Returns:
            Dict with 'reason', 'actor', 'timestamp', 'action' or None.
        """
        from audit.models import ActionLog

        latest = ActionLog.objects.filter(
            related_hash=self.hash_value,
            action_type__in=['UPLOAD_REJECTED', 'UPLOAD_UNPUBLISHED'],
        ).order_by('-timestamp').first()

        if not latest:
            return None

        reason = ''
        if latest.details and isinstance(latest.details, dict):
            reason = latest.details.get('reason', '')

        return {
            'reason': reason,
            'actor': latest.actor.username if latest.actor else 'System',
            'timestamp': latest.timestamp,
            'action': latest.get_action_type_display(),
        }

    def get_all_action_history(self) -> list:
        """
        Get the complete action history for this upload.

        Returns:
            List of ActionLog entries ordered by most recent first.
        """
        from audit.models import ActionLog

        return ActionLog.objects.filter(
            related_hash=self.hash_value,
        ).select_related('actor').order_by('-timestamp')


class LiveState(models.Model):
    """
    Tracks what is currently deployed in test and production.

    This table controls what users actually see. Changes here trigger
    hard-link operations that point working directories to the correct
    archive content.
    """

    environment = models.CharField(
        max_length=20,
        choices=ENVIRONMENT_CHOICES,
        default=ENV_TEST,
        help_text='Deployment environment (TEST or PRODUCTION).'
    )
    folder_name = models.CharField(
        max_length=255,
        help_text='Name of the deployed content package.'
    )
    current_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text='Hash of the currently deployed content.'
    )
    working_path = models.CharField(
        max_length=500,
        help_text='Filesystem path to the working deployment.'
    )
    source_upload = models.ForeignKey(
        UploadHistory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='live_states',
        help_text='The UploadHistory record this deployment came from.'
    )
    last_updated = models.DateTimeField(
        auto_now=True,
        help_text='When this deployment was last changed.'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='live_state_changes',
        help_text='The user who last modified this deployment.'
    )

    class Meta:
        verbose_name = 'Live Deployment'
        verbose_name_plural = 'Live Deployments'
        unique_together = ['environment', 'current_hash']

    def __str__(self):
        return (
            f"{self.environment}: {self.folder_name} "
            f"({self.current_hash[:8]}...)"
        )