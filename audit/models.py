"""
Every user action (upload, approve, reject, publish, delete, restore)
is recorded here with before/after state snapshots to enable:
  - Complete audit trail
  - Full reversibility of any action
"""

from django.conf import settings
from django.db import models

from content.constants import ACTION_TYPE_CHOICES


class ActionLog(models.Model):
    """
    Immutable record of every action performed in the system.

    Stores JSON snapshots of the entity's state before and after each
    action, enabling full reconstruction of history and undo operations.
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='action_logs',
        help_text='The user who performed this action.'
    )
    action_type = models.CharField(
        max_length=50,
        choices=ACTION_TYPE_CHOICES,
        db_index=True,
        help_text='The type of action performed.'
    )
    entity_type = models.CharField(
        max_length=50,
        default='upload',
        help_text='The type of object this action affected.'
    )
    entity_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='The database ID of the affected object.'
    )
    related_hash = models.CharField(
        max_length=64,
        db_index=True,
        blank=True,
        default='',
        help_text='The content hash associated with this action.'
    )
    old_state = models.JSONField(
        null=True,
        blank=True,
        help_text='JSON snapshot of the entity state BEFORE the action.'
    )
    new_state = models.JSONField(
        null=True,
        blank=True,
        help_text='JSON snapshot of the entity state AFTER the action.'
    )
    details = models.JSONField(
        null=True,
        blank=True,
        help_text='Additional context (file counts, reasons, etc.).'
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text='When this action occurred.'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text='IP address of the actor.'
    )

    class Meta:
        verbose_name = 'Action Log'
        verbose_name_plural = 'Action Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['action_type', 'timestamp']),
            models.Index(fields=['related_hash', 'timestamp']),
        ]

    def __str__(self):
        actor_name = self.actor.username if self.actor else 'System'
        return (
            f"[{self.timestamp:%Y-%m-%d %H:%M}] "
            f"{actor_name} → {self.action_type} "
            f"({self.related_hash[:8]}...)"
        )