"""
Constants used across the content management system.

Centralizes status codes, action types, and environment identifiers
to prevent magic strings throughout the codebase.
"""

import os


# CONTENT HASHING SALT (loaded from environment)

SALT_VALUE = os.environ.get(
    'SALT_VALUE',
    'default-dev-salt-change-me-in-production' #can be changeed in production
)




# UPLOAD STATUS WORKFLOW

STATUS_PENDING = 'PENDING'
STATUS_APPROVED = 'APPROVED'
STATUS_REJECTED = 'REJECTED'
STATUS_PUBLISHED = 'PUBLISHED'
STATUS_UNPUBLISHED = 'UNPUBLISHED'
STATUS_DELETED = 'DELETED'
STATUS_ARCHIVED = 'ARCHIVED'

STATUS_CHOICES = [
    (STATUS_PENDING, 'Pending Review'),
    (STATUS_APPROVED, 'Approved'),
    (STATUS_REJECTED, 'Rejected'),
    (STATUS_PUBLISHED, 'Published'),
    (STATUS_UNPUBLISHED, 'Unpublished'),
    (STATUS_DELETED, 'Deleted'),
    (STATUS_ARCHIVED, 'Archived'),
]

# AUDIT ACTION TYPES

ACTION_UPLOAD_CREATED = 'UPLOAD_CREATED'
ACTION_UPLOAD_APPROVED = 'UPLOAD_APPROVED'
ACTION_UPLOAD_REJECTED = 'UPLOAD_REJECTED'
ACTION_UPLOAD_PUBLISHED = 'UPLOAD_PUBLISHED'
ACTION_UPLOAD_UNPUBLISHED = 'UPLOAD_UNPUBLISHED'
ACTION_UPLOAD_DELETED = 'UPLOAD_DELETED'
ACTION_UPLOAD_RESTORED = 'UPLOAD_RESTORED'
ACTION_UPLOAD_REUPLOADED = 'UPLOAD_REUPLOADED'


ACTION_TYPE_CHOICES = [
    (ACTION_UPLOAD_CREATED, 'Upload Created'),
    (ACTION_UPLOAD_APPROVED, 'Upload Approved'),
    (ACTION_UPLOAD_REJECTED, 'Upload Rejected'),
    (ACTION_UPLOAD_PUBLISHED, 'Upload Published'),
    (ACTION_UPLOAD_UNPUBLISHED, 'Upload Unpublished'),
    (ACTION_UPLOAD_DELETED, 'Upload Deleted'),
    (ACTION_UPLOAD_REUPLOADED, 'Upload Reuploaded'),
    (ACTION_UPLOAD_RESTORED, 'Upload Restored'),
]


# DEPLOYMENT ENVIRONMENTS

ENV_TEST = 'TEST'
ENV_PRODUCTION = 'PRODUCTION'

ENVIRONMENT_CHOICES = [
    (ENV_TEST, 'Test'),
    (ENV_PRODUCTION, 'Production'),
]

