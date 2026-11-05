"""
Custom user model with role-based access control.

Two roles exist:
  - Creator:  uploads content folders
  - Approver: reviews, publishes, and manages content
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """Extended user model with a role field for access control."""

    ROLE_CREATOR = 'creator'
    ROLE_APPROVER = 'approver'

    ROLE_CHOICES = [
        (ROLE_CREATOR, 'Creator'),
        (ROLE_APPROVER, 'Approver'),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_CREATOR,
        help_text='Determines the user\'s permissions within the system.'
    )

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['username']

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_creator(self):
        """Check if the user has the Creator role."""
        return self.role == self.ROLE_CREATOR

    @property
    def is_approver(self):
        """Check if the user has the Approver role."""
        return self.role == self.ROLE_APPROVER