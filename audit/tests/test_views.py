"""Tests for audit log views."""

from django.test import TestCase, Client
from django.urls import reverse

from audit.models import ActionLog
from content.tests.helpers import create_test_users, login_as_user


class AuditLogViewTests(TestCase):
    """Verify audit log page rendering and CSV export."""

    def setUp(self):
        self.client = Client()
        self.creator, self.approver = create_test_users()

    def test_logs_page_renders(self):
        login_as_user(self.client, self.approver)
        response = self.client.get(reverse('logs'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SYSTEM AUDIT LOGS')

    def test_logs_page_requires_login(self):
        response = self.client.get(reverse('logs'))
        self.assertEqual(response.status_code, 302)

    def test_export_csv_returns_csv_file(self):
        login_as_user(self.client, self.approver)
        response = self.client.get(reverse('export_logs'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])