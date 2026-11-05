"""Tests for content management views."""

from django.test import TestCase, Client
from django.urls import reverse

from content.constants import (
    STATUS_PENDING, STATUS_APPROVED, STATUS_PUBLISHED, STATUS_DELETED,
)
from content.models import UploadHistory, LiveState
from content.tests.helpers import create_test_users, login_as_user


class DashboardViewTests(TestCase):
    """Verify dashboard rendering based on user role."""

    def setUp(self):
        self.client = Client()
        self.creator, self.approver = create_test_users()

    def test_creator_sees_creator_dashboard(self):
        login_as_user(self.client, self.creator)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'MY UPLOADS')

    def test_approver_sees_approver_dashboard(self):
        login_as_user(self.client, self.approver)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'APPROVER CONTROL CENTER')

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)


class UploadViewTests(TestCase):
    """Verify upload page access control."""

    def setUp(self):
        self.client = Client()
        self.creator, self.approver = create_test_users()

    def test_upload_page_renders_for_creator(self):
        login_as_user(self.client, self.creator)
        response = self.client.get(reverse('upload'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'UPLOAD NEW CONTENT')

    def test_upload_page_blocked_for_approver(self):
        login_as_user(self.client, self.approver)
        response = self.client.get(reverse('upload'))
        self.assertEqual(response.status_code, 403)


class ApprovalWorkflowTests(TestCase):
    """Verify approve/reject/publish/unpublish/delete/restore actions."""

    def setUp(self):
        self.client = Client()
        self.creator, self.approver = create_test_users()
        self.upload = UploadHistory.objects.create(
            folder_name='Test-Upload',
            hash_value='a' * 64,
            archive_path='/tmp/fake',
            status=STATUS_PENDING,
            uploaded_by=self.creator,
        )

    def test_approve_changes_status(self):
        login_as_user(self.client, self.approver)
        response = self.client.post(
            reverse('approve_upload', kwargs={'pk': self.upload.pk})
        )
        self.upload.refresh_from_db()
        self.assertEqual(self.upload.status, STATUS_APPROVED)
        self.assertEqual(response.status_code, 302)

    def test_approve_requires_approver_role(self):
        login_as_user(self.client, self.creator)
        response = self.client.post(
            reverse('approve_upload', kwargs={'pk': self.upload.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_approve_requires_pending_status(self):
        self.upload.status = STATUS_PUBLISHED
        self.upload.save()
        login_as_user(self.client, self.approver)
        response = self.client.post(
            reverse('approve_upload', kwargs={'pk': self.upload.pk})
        )
        self.upload.refresh_from_db()
        self.assertNotEqual(self.upload.status, STATUS_APPROVED)