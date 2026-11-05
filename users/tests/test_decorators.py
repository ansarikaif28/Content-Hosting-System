"""Tests for role-based access control decorators."""

from django.test import TestCase, Client, RequestFactory
from django.urls import reverse

from users.models import CustomUser


class RoleRequiredDecoratorTests(TestCase):
    """Verify that role-based decorators restrict access correctly."""

    def setUp(self):
        self.client = Client()
        self.creator = CustomUser.objects.create_user(
            username='creator', password='testpass123!', role='creator'
        )
        self.approver = CustomUser.objects.create_user(
            username='approver', password='testpass123!', role='approver'
        )

    def test_creator_can_access_upload_page(self):
        self.client.login(username='creator', password='testpass123!')
        response = self.client.get(reverse('upload'))
        self.assertEqual(response.status_code, 200)

    def test_approver_cannot_access_upload_page(self):
        self.client.login(username='approver', password='testpass123!')
        response = self.client.get(reverse('upload'))
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_is_redirected(self):
        response = self.client.get(reverse('upload'))
        self.assertEqual(response.status_code, 302)