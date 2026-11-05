from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core import mail
from unittest.mock import patch

from users.models import CustomUser
from users.forms import CreatorRegistrationForm

User = get_user_model()

class UsersTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_customuser_model(self):
        user = CustomUser.objects.create_user(username='testuser', password='pass123!', role='creator')
        self.assertTrue(user.is_creator)
        self.assertFalse(user.is_approver)
        user.role = 'approver'
        user.save()
        self.assertTrue(user.is_approver)

    def test_creator_registration_form(self):
        data = {
            'username': 'newcreator',
            'email': 'creator@example.com',
            'password1': 'strongpass123!',
            'password2': 'strongpass123!',
        }
        form = CreatorRegistrationForm(data)
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.role, 'creator')
        self.assertEqual(user.username, 'newcreator')

        # Invalid
        data['password2'] = 'different'
        form = CreatorRegistrationForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)

    def test_registration_view(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)

        data = {
            'username': 'newcreator2',
            'email': 'creator2@example.com',
            'password1': 'strongpass123!',
            'password2': 'strongpass123!',
        }
        response = self.client.post(reverse('register'), data)
        self.assertRedirects(response, reverse('dashboard'))
        user = User.objects.get(username='newcreator2')
        self.assertEqual(user.role, 'creator')

    def test_login_view(self):
        User.objects.create_user(username='loginuser', password='pass123!', role='creator')
        response = self.client.post(reverse('login'), {'username': 'loginuser', 'password': 'pass123!'})
        self.assertEqual(response.status_code, 302)

    @patch('django.core.mail.backends.base.BaseEmailBackend.send_messages')
    def test_password_reset(self, mock_send):
        User.objects.create_user(username='resetuser', password='pass', email='reset@example.com')
        response = self.client.post(reverse('password_reset'), {'email': 'reset@example.com'})
        self.assertEqual(mock_send.call_count, 1)

# Discover other tests
from . import test_decorators, test_models, test_views

