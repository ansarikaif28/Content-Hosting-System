"""
The hash is computed over the folder name, all file paths and contents,
then salted with a value to prevent external hash prediction.
"""

import hashlib
import struct
from pathlib import Path

from django.conf import settings


def generate_content_hash(folder_path: Path) -> str:
    """
    Generate a salted SHA-256 hash of an entire folder's contents.

    Algorithm:
        1. Hash the folder name itself to distinguish identically-structured folders.
        2. Collect all files recursively, sorted by relative path.
        3. For each file, hash the relative path length, relative path,
           file size, and file contents — preventing boundary ambiguity.
        4. Include empty directory paths to detect structural changes.
        5. Append the salt value from settings.
        6. Return the hex digest.

    Args:
        folder_path: Path to the folder to hash.

    Returns:
        A 64-character lowercase hex string (SHA-256 digest).

    Raises:
        FileNotFoundError: If the folder doesn't exist.
        ValueError: If the salt is not configured in settings.
        OSError: If a symlink points outside the folder tree.
    """
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    if not folder_path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {folder_path}")

    salt = getattr(settings, 'SALT_VALUE', None)
    if not salt:
        raise ValueError(
            "settings.SALT_VALUE must be set to a non-empty string. "
            "The default fallback is intentionally removed for security."
        )

    folder_path = folder_path.resolve()
    hasher = hashlib.sha256()

    # ------------------------------------------------------------------
    # Hash the folder name so that identically-structured folders
    # with different names (e.g. test-product vs test-production)
    # produce different digests.
    # ------------------------------------------------------------------
    folder_name = folder_path.name
    folder_name_bytes = folder_name.encode('utf-8')
    hasher.update(b'FOLDER_NAME')
    hasher.update(struct.pack('>Q', len(folder_name_bytes)))
    hasher.update(folder_name_bytes)

    # Collect all entries recursively, sorted by relative path
    all_entries = sorted(
        folder_path.rglob('*'),
        key=lambda p: str(p.relative_to(folder_path)).replace('\\', '/')
    )

    for entry_path in all_entries:
        resolved = entry_path.resolve()

        # Guard against symlinks that escape the folder tree
        if entry_path.is_symlink():
            try:
                resolved.relative_to(folder_path)
            except ValueError:
                raise OSError(
                    f"Symlink escapes folder tree: {entry_path} -> {resolved}"
                )

        relative_path = entry_path.relative_to(folder_path)
        normalized_path = str(relative_path).replace('\\', '/')
        path_bytes = normalized_path.encode('utf-8')

        if entry_path.is_file():
            hasher.update(b'FILE')
            hasher.update(struct.pack('>Q', len(path_bytes)))
            hasher.update(path_bytes)

            file_size = entry_path.stat().st_size
            hasher.update(struct.pack('>Q', file_size))

            bytes_read = 0
            with open(entry_path, 'rb') as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    bytes_read += len(chunk)
                    hasher.update(chunk)

            if bytes_read != file_size:
                raise OSError(
                    f"File size changed during read: {entry_path} "
                    f"(expected {file_size}, read {bytes_read})"
                )

        elif entry_path.is_dir():
            if not any(entry_path.iterdir()):
                hasher.update(b'EMPTY_DIR')
                hasher.update(struct.pack('>Q', len(path_bytes)))
                hasher.update(path_bytes)

    # Append the salt to prevent hash prediction
    salt_bytes = salt.encode('utf-8')
    hasher.update(b'SALT')
    hasher.update(struct.pack('>Q', len(salt_bytes)))
    hasher.update(salt_bytes)

    return hasher.hexdigest()