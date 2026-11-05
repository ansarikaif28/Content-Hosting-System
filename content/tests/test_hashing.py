"""Tests for the content hashing utility."""

import os
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings

from content.utils.hashing import generate_content_hash
from content.tests.helpers import create_valid_test_folder


class ContentHashingTests(TestCase):
    """Verify SHA-256 hashing produces correct, deterministic results."""

    def setUp(self):
        import tempfile
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_folder = create_valid_test_folder(
            self.temp_dir, 'hash-test'
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.temp_dir), ignore_errors=True)

    def test_hash_is_deterministic(self):
        """Same content should always produce the same hash."""
        hash1 = generate_content_hash(self.test_folder)
        hash2 = generate_content_hash(self.test_folder)
        self.assertEqual(hash1, hash2)

    def test_hash_is_64_characters(self):
        """SHA-256 hex digest must be exactly 64 characters."""
        result = generate_content_hash(self.test_folder)
        self.assertEqual(len(result), 64)

    def test_hash_changes_with_different_content(self):
        """Different file content must produce a different hash."""
        hash1 = generate_content_hash(self.test_folder)

        # Modify a file
        (self.test_folder / 'en' / 'index.html').write_text('<h1>Changed</h1>')
        hash2 = generate_content_hash(self.test_folder)

        self.assertNotEqual(hash1, hash2)

    @override_settings(SALT_VALUE='salt-A')
    def test_hash_changes_with_different_salt(self):
        """Different salt values must produce different hashes."""
        hash1 = generate_content_hash(self.test_folder)

        with self.settings(SALT_VALUE='salt-B'):
            hash2 = generate_content_hash(self.test_folder)

        self.assertNotEqual(hash1, hash2)

    def test_hash_raises_on_missing_folder(self):
        """Should raise FileNotFoundError for non-existent path."""
        with self.assertRaises(FileNotFoundError):
            generate_content_hash(Path('/nonexistent/folder'))