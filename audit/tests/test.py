from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import csv
from io import StringIO

from audit.models import ActionLog
from audit.services import log_action, get_state_snapshot
from content.models import UploadHistory
User = get_user_model()

class AuditTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.creator = User.objects.create_user(username='creator', password='pass', role='creator')
        self.approver = User.objects.create_user(username='approver', password='pass', role='approver')
        self.upload = UploadHistory.objects.create(folder_name='test', hash_value='test123', status='PENDING', uploaded_by=self.creator)

    def test_actionlog_model(self):
        # Create
        log = ActionLog.objects.create(
            actor=self.creator,
            action_type='UPLOAD_CREATED',
            related_hash='abc123def456...'
        )
        self.assertIn('creator → UPLOAD_CREATED', str(log))

        # Read/JSON
        log.old_state = {'test': 'data'}
        log.save()
        saved = ActionLog.objects.get(id=log.id)
        self.assertEqual(saved.old_state, {'test': 'data'})

        # Delete
        log.delete()
        self.assertEqual(ActionLog.objects.count(), 0)

    def test_get_state_snapshot(self):
        snapshot = get_state_snapshot(self.upload)
        expected_keys = ['id', 'folder_name', 'hash_value', 'status']
        for key in expected_keys:
            self.assertIn(key, snapshot)

    def test_log_action(self):
        old_state = {'status': 'pending'}
        log = log_action(
            actor=self.creator,
            action_type='TEST_ACTION',
            related_hash='test_hash',
            old_state=old_state
        )
        self.assertEqual(log.action_type, 'TEST_ACTION')
        self.assertEqual(log.old_state, old_state)

    def test_action_log_list_view(self):
        self.client.login(username='approver', password='pass')
        # Create logs for filtering
        ActionLog.objects.create(actor=self.approver, action_type='UPLOAD_APPROVED')
        
        response = self.client.get(reverse('logs'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'audit/logs.html')

        # Filter
        response = self.client.get(reverse('logs'), {'action_type': 'UPLOAD_APPROVED'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'UPLOAD_APPROVED')

    def test_export_logs_csv_view(self):
        self.client.login(username='approver', password='pass')
        log = ActionLog.objects.create(actor=self.approver, action_type='EXPORT_TEST')
        response = self.client.get(reverse('export_logs'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment; filename="audit_logs_', response['Content-Disposition'])
        content = response.content.decode()
        self.assertIn('EXPORT_TEST', content)

    def test_unauthenticated_access(self):
        response = self.client.get(reverse('logs'))
        self.assertRedirects(response, '/login/?next=/logs/')

# Discover other tests
from . import test_services, test_views

