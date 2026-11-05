"""
Audit logging service layer.

Provides a clean API for recording actions throughout the system.
All business logic modules should call these functions rather than
creating ActionLog entries directly.
"""

import logging

from audit.models import ActionLog

logger = logging.getLogger(__name__)


def get_client_ip_address(request) -> str | None:
    """
    Extract the client's IP address from the Django request.
    
    """
    if request is None:
        return None

    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def get_state_snapshot(upload) -> dict:
    """
    Create a JSON-serializable snapshot of an UploadHistory instance.

    This snapshot is stored in ActionLog.old_state / new_state
    to enable full reversibility.

    Args:
        upload: An UploadHistory model instance.

    Returns:
        Dictionary with all relevant state fields.
    """
    return {
        'id': upload.id,
        'folder_name': upload.folder_name,
        'hash_value': upload.hash_value,
        'status': upload.status,
        'archive_path': upload.archive_path,
        'uploaded_by': (
            upload.uploaded_by.username if upload.uploaded_by else None
        ),
        'uploaded_at': (
            upload.uploaded_at.isoformat() if upload.uploaded_at else None
        ),
        'file_count': upload.file_count,
        'total_size': upload.total_size,
    }


def log_action(
    actor,
    action_type: str,
    entity_type: str = 'upload',
    entity_id: int = None,
    related_hash: str = '',
    old_state: dict = None,
    new_state: dict = None,
    details: dict = None,
    request=None,
) -> ActionLog:
    """
    Record an action in the centralized audit log.

    This is the single entry point for all logging. Every state change
    in the system should flow through this function.

    Args:
        actor:        The user performing the action.
        action_type:  One of the ACTION_TYPE_CHOICES constants.
        entity_type:  The type of entity affected (default: 'upload').
        entity_id:    The database ID of the affected entity.
        related_hash: The content hash associated with the action.
        old_state:    State snapshot before the action.
        new_state:    State snapshot after the action.
        details:      Additional context information.
        request:      The Django request (for IP extraction).

    Returns:
        The created ActionLog instance.
    """
    ip_address = get_client_ip_address(request)

    log_entry = ActionLog.objects.create(
        actor=actor,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        related_hash=related_hash,
        old_state=old_state,
        new_state=new_state,
        details=details,
        ip_address=ip_address,
    )

    actor_name = actor.username if actor else 'System'
    logger.info(
        "ACTION: %s by %s on %s #%s (hash: %s...)",
        action_type, actor_name, entity_type,
        entity_id, related_hash[:8] if related_hash else 'N/A',
    )

    return log_entry