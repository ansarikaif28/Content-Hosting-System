"""Tests for the audit logging service layer."""

from django.test import TestCase, RequestFactory

from audit.models import ActionLog
from audit.services import log_action, get_state_snapshot
from content.constants import ACTION_UPLOAD_CREATED, STATUS_PENDING
from content.models import UploadHistory
from content.tests.helpers import create_test_users


class LogActionServiceTests(TestCase):
    """Verify that the logging service records actions correctly."""

    def setUp(self):
        self.creator, self.approver = create_test_users()
        self.upload = UploadHistory.objects.create(
            folder_name='LogTest',
            hash_value='b' * 64,
            archive_path='/tmp/log-test',
            status=STATUS_PENDING,
            uploaded_by=self.creator,
        )

    def test_log_action_creates_entry(self):
        log_action(
            actor=self.creator,
            action_type=ACTION_UPLOAD_CREATED,
            entity_id=self.upload.id,
            related_hash=self.upload.hash_value,
        )
        self.assertEqual(ActionLog.objects.count(), 1)

    def test_log_action_stores_state_snapshots(self):
        old = {'status': 'OLD'}
        new = {'status': 'NEW'}
        entry = log_action(
            actor=self.creator,
            action_type=ACTION_UPLOAD_CREATED,
            old_state=old,
            new_state=new,
        )
        self.assertEqual(entry.old_state, old)
        self.assertEqual(entry.new_state, new)

    def test_get_state_snapshot_includes_key_fields(self):
        snapshot = get_state_snapshot(self.upload)
        self.assertIn('id', snapshot)
        self.assertIn('folder_name', snapshot)
        self.assertIn('hash_value', snapshot)
        self.assertIn('status', snapshot)
        self.assertEqual(snapshot['folder_name'], 'LogTest')

    def test_log_action_captures_ip_from_request(self):
        factory = RequestFactory()
        request = factory.post('/fake/', REMOTE_ADDR='192.168.1.100')
        entry = log_action(
            actor=self.creator,
            action_type=ACTION_UPLOAD_CREATED,
            request=request,
        )
        self.assertEqual(entry.ip_address, '192.168.1.100')