from django.test import TestCase, Client
from django.contrib.auth import get, get_user_model
from django.urls import reverse
from django.conf import settings
from unittest.mock import patch, MagicMock
import json
import os

from audit.models import ActionLog
from . import test_filesystem, test_hashing, test_validators, test_views

from content.models import UploadHistory, LiveState
from content.forms import FolderUploadForm
from content.constants import STATUS_PENDING, STATUS_APPROVED
from audit.services import log_action
from content.utils.hashing import generate_content_hash
User = get_user_model()

class ContentTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.creator = User.objects.create_user('creator', 'pass', role='creator')
        self.approver = User.objects.create_user('approver', 'pass', role='approver')

    def test_uploadhistory_model(self):
        upload = UploadHistory.objects.create(folder_name='test', hash_value='abc123', status=STATUS_PENDING)
        self.assertEqual(upload.get_test_url(), '/test/abc123/en/index.html')
        self.assertEqual(upload.get_total_size_display(), '0.0 B')

    def test_livestate_model(self):
        upload = UploadHistory.objects.create(folder_name='live', hash_value='def456')
        LiveState.objects.create(environment='test', folder_name='live', current_hash='def456')
        self.assertEqual(LiveState.objects.count(), 1)

    def test_folderupload_form(self):
        data = {'folder_name': 'valid-name', 'folder_files': [MagicMock()]}
        form = FolderUploadForm(data=data, files={'folder_files': [MagicMock()]})
        self.assertTrue(form.is_valid())
        data = {'folder_name': 'invalid@name'}
        form = FolderUploadForm(data)
        self.assertFalse(form.is_valid())

    @patch('content.utils.filesystem.archive_upload')
    @patch('content.utils.hashing.generate_content_hash')
    @patch('content.utils.filesystem.deploy_to_test')
    def test_upload_content_view(self, mock_deploy, mock_hash, mock_archive):
        mock_hash.return_value = 'mockhash'
        self.client.login(username='creator', password='pass')
        files = {'folder_files': [MagicMock()]}
        data = {'folder_name': 'test-folder'}
        response = self.client.post(
            reverse('upload'), 
            data=data,
            files=files
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(UploadHistory.objects.count(), 1)

    def test_approve_upload_view(self):
        upload = UploadHistory.objects.create(folder_name='test', hash_value='hash1', status=STATUS_PENDING)
        self.client.login(username='approver', password='pass')
        self.client.post(reverse('approve_upload', args=[upload.pk]))
        upload.refresh_from_db()
        self.assertEqual(upload.status, STATUS_APPROVED)

    def test_role_required_decorator(self):
        self.client.login(username='creator', password='pass')
        response = self.client.post(reverse('approve_upload', args=[1]), follow=True)
        self.assertContains(response, 'permission', status_code=403, msg_prefix="Role check")

    @patch('content.views._serve_content_file')
    def test_serve_test_content(self, mock_serve):
        self.client.login(username='approver', password='pass')
        response = self.client.get('/test/hash123/en/index.html')
        mock_serve.assert_called()

    def test_content_serving_security(self):
        response = self.client.get('/test/../secret/file.html')
        self.assertNotEqual(response.status_code, 200)

    def test_dashboard_role_based(self):
        self.client.login(username='creator', password='pass')
        response = self.client.get(reverse('dashboard'))
        self.assertIn(response.status_code, [200, 302])

        self.client.login(username='approver', password='pass')
        response = self.client.get(reverse('dashboard'))
        self.assertIn(response.status_code, [200, 302])

    def test_log_action_integration(self):
        old_count = ActionLog.objects.count()
        self.client.login(username='approver', password='pass')
        upload = UploadHistory.objects.create(folder_name='int-test', hash_value='inthash')
        self.client.post(reverse('approve_upload', args=[upload.pk]))
        self.assertGreater(ActionLog.objects.count(), old_count)

