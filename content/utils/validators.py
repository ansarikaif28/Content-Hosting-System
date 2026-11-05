"""
Validation utilities for uploaded folder structure and file safety.

These validators enforce the required directory structure and prevent
malicious file uploads.

Required structure:
    <root>/
        en/
            index.html
        de/
            index.html
        shared-assets/

Everything else (assets/, style.css, extra folders) is OPTIONAL.
"""

import re
from pathlib import Path

from django.conf import settings


def validate_folder_structure(folder_path: Path) -> tuple[bool, list[str]]:
    """
    Validate that the uploaded folder has the required directory structure.

    ONLY these are required:
        - en/ directory exists
        - en/index.html file exists
        - de/ directory exists
        - de/index.html file exists
        - shared-assets/ directory exists

    Everything else (style.css, assets/, images/, etc.) is OPTIONAL
    and will NOT cause validation to fail.

    Args:
        folder_path: Path to the root of the uploaded folder.

    Returns:
        A tuple of (is_valid, error_messages).
        If valid: (True, [])
        If invalid: (False, ['error 1', 'error 2', ...])
    """
    errors = []

    # Check root folder exists
    if not folder_path.exists() or not folder_path.is_dir():
        return False, ['Root folder does not exist or is not a directory.']

    # --- Check en/ directory and en/index.html ---
    en_dir = folder_path / 'en'
    if not en_dir.exists() or not en_dir.is_dir():
        errors.append('Missing required directory: en/')
    else:
        en_index = en_dir / 'index.html'
        if not en_index.exists() or not en_index.is_file():
            errors.append('Missing required file: en/index.html')

    # --- Check de/ directory and de/index.html ---
    de_dir = folder_path / 'de'
    if not de_dir.exists() or not de_dir.is_dir():
        errors.append('Missing required directory: de/')
    else:
        de_index = de_dir / 'index.html'
        if not de_index.exists() or not de_index.is_file():
            errors.append('Missing required file: de/index.html')

    # --- Check shared-assets/ directory ---
    shared_assets_dir = folder_path / 'shared-assets'
    if not shared_assets_dir.exists() or not shared_assets_dir.is_dir():
        errors.append('Missing required directory: shared-assets/')

    # --- That's it. Nothing else is required. ---

    is_valid = len(errors) == 0
    return is_valid, errors


def validate_file_safety(folder_path: Path) -> tuple[bool, list[str]]:
    """
    Validate that the uploaded folder contains no malicious content.

    Security checks performed:
        1. No symbolic links anywhere in the tree.
        2. No path traversal patterns (..) in any path component.
        3. All file extensions are on the allowed list.
        4. No individual file exceeds the maximum upload size.
        5. No null bytes in paths.

    Args:
        folder_path: Path to the root of the uploaded folder.

    Returns:
        A tuple of (is_safe, error_messages).
    """
    errors = []
    allowed_extensions = getattr(settings, 'ALLOWED_FILE_EXTENSIONS', [])
    max_size_bytes = getattr(
        settings, 'MAX_UPLOAD_SIZE_BYTES', 500 * 1024 * 1024
    )

    for item in folder_path.rglob('*'):
        relative = str(item.relative_to(folder_path))

        # Check for symbolic links
        if item.is_symlink():
            errors.append(f'Symbolic links are not allowed: {relative}')

        # Check for path traversal
        if '..' in relative.split('/') or '..' in relative.split('\\'):
            errors.append(f'Path traversal detected: {relative}')

        # Check for null bytes
        if '\x00' in str(item):
            errors.append(f'Null byte in path: {relative}')

        # Validate file-specific constraints (skip directories)
        if item.is_file():
            # Check file extension
            suffix = item.suffix.lower()
            if suffix and suffix not in allowed_extensions:
                errors.append(
                    f'Disallowed file extension "{suffix}": {relative}'
                )

            # Check file size
            try:
                file_size = item.stat().st_size
                if file_size > max_size_bytes:
                    size_mb = file_size / (1024 * 1024)
                    errors.append(
                        f'File too large ({size_mb:.1f}MB): {relative}'
                    )
            except OSError:
                errors.append(f'Cannot read file: {relative}')

    is_safe = len(errors) == 0
    return is_safe, errors


def validate_folder_name(name: str) -> tuple[bool, str]:
    """
    Validate that a folder name contains only safe characters.

    Allowed characters: letters, digits, hyphens, underscores.

    Args:
        name: The folder name to validate.

    Returns:
        A tuple of (is_valid, error_message).
    """
    if not name:
        return False, 'Folder name cannot be empty.'

    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        return False, (
            'Folder name may only contain letters, digits, '
            'hyphens, and underscores.'
        )

    if len(name) > 255:
        return False, 'Folder name cannot exceed 255 characters.'

    return True, ''