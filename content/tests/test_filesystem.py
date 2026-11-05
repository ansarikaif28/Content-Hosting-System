"""Tests for filesystem operations (archive, deploy, hard links)."""

import os
import shutil
import tempfile
from pathlib import Path

from django.test import TestCase
from django.conf import settings

from content.utils.filesystem import (
    archive_upload, deploy_to_test, deploy_to_production,
    undeploy_from_test, undeploy_from_production,
    move_to_deleted, restore_from_deleted,
    DuplicateUploadError, ArchiveNotFoundError,
)
from content.tests.helpers import create_valid_test_folder


class FilesystemOperationsTests(TestCase):
    """Verify filesystem operations for the hard-link architecture."""

    def setUp(self):
        """Create isolated temp directories and override Django settings."""
        self.temp_dir = Path(tempfile.mkdtemp())

        # Create isolated storage directories
        self.archive_dir = self.temp_dir / 'archive'
        self.working_dir = self.temp_dir / 'working'
        self.archive_dir.mkdir(parents=True)
        (self.working_dir / 'test').mkdir(parents=True)
        (self.working_dir / 'production').mkdir(parents=True)

        # Override Django settings to use temp directories
        self._original_archive_dir = settings.ARCHIVE_DIR
        self._original_working_dir = settings.WORKING_DIR
        settings.ARCHIVE_DIR = self.archive_dir
        settings.WORKING_DIR = self.working_dir

        # Create a valid source folder for uploads
        self.source_folder = create_valid_test_folder(
            self.temp_dir, 'source'
        )

    def tearDown(self):
        """Restore original settings and clean up temp files."""
        settings.ARCHIVE_DIR = self._original_archive_dir
        settings.WORKING_DIR = self._original_working_dir
        shutil.rmtree(str(self.temp_dir), ignore_errors=True)

    # --- Archive Tests ---

    def test_archive_upload_creates_directory(self):
        """Archiving should create a directory with all files."""
        hash_val = 'a' * 64
        result = archive_upload(self.source_folder, hash_val)
        self.assertTrue(result.exists())
        self.assertTrue((result / 'en' / 'index.html').exists())
        self.assertTrue((result / 'de' / 'index.html').exists())

    def test_archive_upload_duplicate_raises_error(self):
        """Archiving the same hash twice should raise DuplicateUploadError."""
        hash_val = 'b' * 64
        archive_upload(self.source_folder, hash_val)
        with self.assertRaises(DuplicateUploadError):
            archive_upload(self.source_folder, hash_val)

    # --- Deploy to Test ---

    def test_deploy_to_test_creates_files(self):
        """Deploying to test should create files in working/test/<hash>/."""
        hash_val = 'c' * 64
        archive_upload(self.source_folder, hash_val)
        test_path = deploy_to_test(hash_val)
        self.assertTrue(test_path.exists())
        self.assertTrue((test_path / 'en' / 'index.html').exists())
        self.assertTrue((test_path / 'de' / 'index.html').exists())

    def test_deploy_to_test_nonexistent_archive_raises_error(self):
        """Deploying a hash with no archive should raise ArchiveNotFoundError."""
        with self.assertRaises(ArchiveNotFoundError):
            deploy_to_test('f' * 64)

    def test_hard_link_shares_inode(self):
        """Hard-linked files should share the same inode as the archive."""
        hash_val = 'd' * 64
        archive_path = archive_upload(self.source_folder, hash_val)
        test_path = deploy_to_test(hash_val)

        archive_file = archive_path / 'en' / 'index.html'
        test_file = test_path / 'en' / 'index.html'

        archive_inode = os.stat(str(archive_file)).st_ino
        test_inode = os.stat(str(test_file)).st_ino
        self.assertEqual(archive_inode, test_inode)

    # --- Deploy to Production ---

    def test_deploy_to_production_creates_files(self):
        """Deploying to production should create files in working/production/<hash>/."""
        hash_val = 'e' * 64
        archive_upload(self.source_folder, hash_val)
        prod_path = deploy_to_production(hash_val)
        self.assertTrue(prod_path.exists())
        self.assertTrue((prod_path / 'en' / 'index.html').exists())
        self.assertTrue((prod_path / 'de' / 'index.html').exists())

    # --- Undeploy ---

    def test_undeploy_from_test_removes_directory(self):
        """Undeploying from test should remove the working/test/<hash>/ directory."""
        hash_val = 'f1' * 32
        archive_upload(self.source_folder, hash_val)
        deploy_to_test(hash_val)
        undeploy_from_test(hash_val)
        self.assertFalse(
            (self.working_dir / 'test' / hash_val).exists()
        )

    def test_undeploy_from_production_removes_directory(self):
        """Undeploying from production should remove the directory."""
        hash_val = 'f2' * 32
        archive_upload(self.source_folder, hash_val)
        deploy_to_production(hash_val)
        undeploy_from_production(hash_val)
        self.assertFalse(
            (self.working_dir / 'production' / hash_val).exists()
        )

    def test_undeploy_preserves_archive(self):
        """Undeploying should NOT delete the archive copy."""
        hash_val = 'f3' * 32
        archive_path = archive_upload(self.source_folder, hash_val)
        deploy_to_test(hash_val)
        undeploy_from_test(hash_val)

        # Test dir gone
        self.assertFalse(
            (self.working_dir / 'test' / hash_val).exists()
        )
        # Archive still exists
        self.assertTrue(archive_path.exists())
        self.assertTrue((archive_path / 'en' / 'index.html').exists())

    # --- Move to Deleted (Soft Delete) ---

    def test_move_to_deleted_removes_working_links(self):
        """Soft-deleting should remove working links but preserve archive."""
        hash_val = 'f4' * 32
        archive_upload(self.source_folder, hash_val)
        deploy_to_test(hash_val)

        archive_path = move_to_deleted(hash_val)

        # Working links removed
        self.assertFalse(
            (self.working_dir / 'test' / hash_val).exists()
        )
        self.assertFalse(
            (self.working_dir / 'production' / hash_val).exists()
        )
        # Archive preserved
        self.assertTrue(
            (self.archive_dir / hash_val).exists(),
            f'Archive should exist at {self.archive_dir / hash_val}'
        )
        self.assertTrue(archive_path.exists())

    def test_move_to_deleted_with_production(self):
        """Soft-deleting production content should also preserve archive."""
        hash_val = 'f5' * 32
        archive_upload(self.source_folder, hash_val)
        deploy_to_production(hash_val)

        move_to_deleted(hash_val)

        self.assertFalse(
            (self.working_dir / 'production' / hash_val).exists()
        )
        self.assertTrue(
            (self.archive_dir / hash_val).exists()
        )

    # --- Restore ---

    def test_restore_from_deleted_redeploys_to_test(self):
        """Restoring should recreate hard links in working/test/."""
        hash_val = 'f6' * 32
        archive_upload(self.source_folder, hash_val)
        deploy_to_test(hash_val)
        move_to_deleted(hash_val)

        # Verify deleted
        self.assertFalse(
            (self.working_dir / 'test' / hash_val).exists()
        )

        # Restore
        test_path = restore_from_deleted(hash_val)

        self.assertTrue(test_path.exists())
        self.assertTrue((test_path / 'en' / 'index.html').exists())
        self.assertTrue((test_path / 'de' / 'index.html').exists())

    def test_restore_nonexistent_archive_raises_error(self):
        """Restoring when archive is gone should raise ArchiveNotFoundError."""
        with self.assertRaises(ArchiveNotFoundError):
            restore_from_deleted('00' * 32)

    # --- Hard Link Independence ---

    def test_deleting_archive_does_not_break_working(self):
        """
        After deploying, deleting the archive should NOT affect
        the working files (hard link independence).
        """
        hash_val = 'f7' * 32
        archive_path = archive_upload(self.source_folder, hash_val)
        test_path = deploy_to_test(hash_val)

        # Read content before deleting archive
        original_content = (test_path / 'en' / 'index.html').read_text()

        # Delete the archive
        shutil.rmtree(str(archive_path))
        self.assertFalse(archive_path.exists())

        # Working files should still be accessible
        self.assertTrue((test_path / 'en' / 'index.html').exists())
        self.assertEqual(
            (test_path / 'en' / 'index.html').read_text(),
            original_content,
        )