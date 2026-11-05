"""
Filesystem operations for the content hosting pipeline.

This module handles all file movements between archive and working
directories using hard links.

Architecture:
    storage/archive/<hash>/        
    storage/working/test/<hash>/   ← Hard links for test preview
    storage/working/production/<hash>/ ← Hard links for live site
"""

import os
import shutil
import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


class DuplicateUploadError(Exception):
    """Raised when an upload with the same hash already exists in the archive."""
    pass


class ArchiveNotFoundError(Exception):
    """Raised when attempting to operate on a non-existent archive."""
    pass


class HardLinkError(Exception):
    """Raised when hard link creation fails."""
    pass


def archive_upload(source_folder: Path, hash_value: str) -> Path:
    """
    Copy uploaded content into the archive.

    Args:
        source_folder: Path to the temporary upload folder.
        hash_value: The SHA-256 hash identifying this content.

    Returns:
        Path to the newly created archive directory.

    Raises:
        DuplicateUploadError: If content with this hash already exists.
        FileNotFoundError: If the source folder doesn't exist.
    """
    archive_path = Path(settings.ARCHIVE_DIR) / hash_value

    if archive_path.exists():
        raise DuplicateUploadError(
            f"Content with hash {hash_value[:12]}... already exists "
            f"in the archive. Please change the name of the folder."
        )

    if not source_folder.exists():
        raise FileNotFoundError(
            f"Source folder not found: {source_folder}"
        )

    try:
        shutil.copytree(str(source_folder), str(archive_path))
        logger.info("Archived upload %s to %s", hash_value[:12], archive_path)
        return archive_path
    except Exception as e:
        if archive_path.exists():
            shutil.rmtree(str(archive_path), ignore_errors=True)
        logger.error("Failed to archive upload %s: %s", hash_value[:12], e)
        raise


def _create_hard_links(source_dir: Path, target_dir: Path) -> None:
    """
    Recursively create hard links from source to target directory.

    Args:
        source_dir: The archive directory containing the original files.
        target_dir: The working directory to link into.

    Raises:
        HardLinkError: If hard link creation fails for any file.
    """
    for source_item in source_dir.rglob('*'):
        relative_path = source_item.relative_to(source_dir)
        target_item = target_dir / relative_path

        if source_item.is_dir():
            target_item.mkdir(parents=True, exist_ok=True)
        elif source_item.is_file():
            target_item.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(str(source_item), str(target_item))
            except OSError as e:
                logger.error(
                    "Hard link failed for %s -> %s: %s",
                    source_item, target_item, e
                )
                raise HardLinkError(
                    f"Failed to create hard link: {source_item} -> {target_item}. "
                    f"Reason: {e}. "
                    f"Ensure source and target are on the same filesystem."
                )


def deploy_to_test(hash_value: str) -> Path:
    """
    Deploy archived content to test environment using hard links.

    Args:
        hash_value: The content hash to deploy.

    Returns:
        Path to the test deployment directory.

    Raises:
        ArchiveNotFoundError: If the archive doesn't exist.
        HardLinkError: If hard link creation fails.
    """
    source = Path(settings.ARCHIVE_DIR) / hash_value
    target = Path(settings.WORKING_DIR) / 'test' / hash_value

    if not source.exists():
        raise ArchiveNotFoundError(
            f"Archive not found for hash {hash_value[:12]}..."
        )

    if target.exists():
        shutil.rmtree(str(target))

    target.mkdir(parents=True, exist_ok=True)
    
    try:
        _create_hard_links(source, target)
    except HardLinkError:
        if target.exists():
            shutil.rmtree(str(target))
        raise

    logger.info("Deployed %s to test environment", hash_value[:12])
    return target


def deploy_to_production(hash_value: str) -> Path:
    """
    Deploy archived content to production environment using hard links.

    Args:
        hash_value: The content hash to deploy.

    Returns:
        Path to the production deployment directory.

    Raises:
        ArchiveNotFoundError: If the archive doesn't exist.
        HardLinkError: If hard link creation fails.
    """
    source = Path(settings.ARCHIVE_DIR) / hash_value
    target = Path(settings.WORKING_DIR) / 'production' / hash_value

    if not source.exists():
        raise ArchiveNotFoundError(
            f"Archive not found for hash {hash_value[:12]}..."
        )

    if target.exists():
        shutil.rmtree(str(target))

    target.mkdir(parents=True, exist_ok=True)
    
    try:
        _create_hard_links(source, target)
    except HardLinkError:
        if target.exists():
            shutil.rmtree(str(target))
        raise

    logger.info("Deployed %s to production environment", hash_value[:12])
    return target


def undeploy_from_test(hash_value: str) -> None:
    """
    Remove content deployment from test environment.

    Args:
        hash_value: The content hash to undeploy.
    """
    target = Path(settings.WORKING_DIR) / 'test' / hash_value
    if target.exists():
        shutil.rmtree(str(target))
        logger.info("Undeployed %s from test environment", hash_value[:12])


def undeploy_from_production(hash_value: str) -> None:
    """
    Remove content deployment from production environment.

    Args:
        hash_value: The content hash to undeploy.
    """
    target = Path(settings.WORKING_DIR) / 'production' / hash_value
    if target.exists():
        shutil.rmtree(str(target))
        logger.info("Undeployed %s from production environment", hash_value[:12])


def move_to_deleted(hash_value: str) -> Path:
    """
    Soft-delete content by removing all working links.

    Args:
        hash_value: The content hash to delete.

    Returns:
        Path to the preserved archive directory.
    """
    undeploy_from_test(hash_value)
    undeploy_from_production(hash_value)

    archive_path = Path(settings.ARCHIVE_DIR) / hash_value
    logger.info("Soft-deleted %s (archive preserved)", hash_value[:12])
    return archive_path


def restore_from_deleted(hash_value: str) -> Path:
    """
    Restore soft-deleted content by redeploying to test environment.

    Args:
        hash_value: The content hash to restore.

    Returns:
        Path to the restored test deployment.

    Raises:
        ArchiveNotFoundError: If the archive has been pruned.
        HardLinkError: If hard link creation fails.
    """
    archive_path = Path(settings.ARCHIVE_DIR) / hash_value
    if not archive_path.exists():
        raise ArchiveNotFoundError(
            f"Cannot restore: archive for {hash_value[:12]}... "
            f"has been pruned or does not exist."
        )

    return deploy_to_test(hash_value)


def remove_archive(hash_value: str) -> None:
    """
    Permanently remove archived content.

    Args:
        hash_value: The content hash whose archive should be removed.

    Raises:
        ArchiveNotFoundError: If the archive does not exist.
    """
    archive_path = Path(settings.ARCHIVE_DIR) / hash_value

    if not archive_path.exists():
        raise ArchiveNotFoundError(
            f"Archive not found for hash {hash_value[:12]}..."
        )

    shutil.rmtree(str(archive_path))
    logger.info("Removed archive for %s", hash_value[:12])


# ============================================================
# Utility Functions (used by other modules)
# ============================================================

def count_files_in_directory(directory: Path) -> int:
    """
    Count the total number of files in a directory tree.
    
    Args:
        directory: Path to the directory.
        
    Returns:
        Number of files in the directory tree.
    """
    if not directory.exists():
        return 0
    return sum(1 for _ in directory.rglob('*') if _.is_file())


def calculate_directory_size(directory: Path) -> int:
    """
    Calculate the total size in bytes of all files in a directory tree.
    
    Args:
        directory: Path to the directory.
        
    Returns:
        Total size in bytes.
    """
    if not directory.exists():
        return 0
    return sum(f.stat().st_size for f in directory.rglob('*') if f.is_file())