"""Tests for authentication and registration views."""

from django.test import TestCase, Client
from django.urls import reverse

from users.models import CustomUser


class LoginViewTests(TestCase):
    """Verify login page rendering and authentication."""

    def setUp(self):
        self.client = Client()
        self.creator = CustomUser.objects.create_user(
            username='alice', password='testpass123!', role='creator'
        )

    def test_login_page_renders_with_correct_template(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/login.html')
        self.assertContains(response, 'CONTENT HOSTING SYSTEM')

    def test_login_page_has_register_link(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, reverse('register'))

    def test_login_success_redirects_to_dashboard(self):
        response = self.client.post(reverse('login'), {
            'username': 'alice', 'password': 'testpass123!'
        })
        self.assertRedirects(response, reverse('dashboard'))

    def test_login_failure_shows_error(self):
        response = self.client.post(reverse('login'), {
            'username': 'alice', 'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid username or password')

    def test_logout_redirects_to_login(self):
        self.client.login(username='alice', password='testpass123!')
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'))

    def test_unauthenticated_dashboard_redirects_to_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('dashboard')}"
        )

    def test_password_reset_page_renders(self):
        response = self.client.get(reverse('password_reset'))
        self.assertEqual(response.status_code, 200)


class RegistrationViewTests(TestCase):
    """Verify Creator self-registration."""

    def setUp(self):
        self.client = Client()

    def test_registration_page_renders(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/register.html')
        self.assertContains(response, 'CREATE ACCOUNT')

    def test_successful_registration_creates_creator(self):
        """A new user should be created with the Creator role."""
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'password1': 'securepass123!',
            'password2': 'securepass123!',
        })
        self.assertRedirects(response, reverse('dashboard'))

        user = CustomUser.objects.get(username='newuser')
        self.assertEqual(user.role, CustomUser.ROLE_CREATOR)
        self.assertTrue(user.is_creator)
        self.assertFalse(user.is_approver)
        self.assertEqual(user.email, 'newuser@test.com')

    def test_registration_auto_logs_in(self):
        """After registration the user should be logged in."""
        self.client.post(reverse('register'), {
            'username': 'autouser',
            'email': 'auto@test.com',
            'password1': 'securepass123!',
            'password2': 'securepass123!',
        })
        # Accessing dashboard should work without login
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_registration_always_creates_creator_role(self):
        """Users cannot register as approver through the form."""
        self.client.post(reverse('register'), {
            'username': 'sneaky',
            'email': 'sneaky@test.com',
            'password1': 'securepass123!',
            'password2': 'securepass123!',
        })
        user = CustomUser.objects.get(username='sneaky')
        self.assertEqual(user.role, CustomUser.ROLE_CREATOR)

    def test_registration_password_mismatch_fails(self):
        response = self.client.post(reverse('register'), {
            'username': 'baduser',
            'email': 'bad@test.com',
            'password1': 'securepass123!',
            'password2': 'differentpass!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            CustomUser.objects.filter(username='baduser').exists()
        )

    def test_registration_short_password_fails(self):
        response = self.client.post(reverse('register'), {
            'username': 'shortpw',
            'email': 'short@test.com',
            'password1': 'abc',
            'password2': 'abc',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            CustomUser.objects.filter(username='shortpw').exists()
        )

    def test_registration_duplicate_username_fails(self):
        CustomUser.objects.create_user(
            username='existing', password='pass123!', role='creator'
        )
        response = self.client.post(reverse('register'), {
            'username': 'existing',
            'email': 'new@test.com',
            'password1': 'securepass123!',
            'password2': 'securepass123!',
        })
        self.assertEqual(response.status_code, 200)

    def test_registration_duplicate_email_fails(self):
        CustomUser.objects.create_user(
            username='first', password='pass123!',
            email='taken@test.com', role='creator'
        )
        response = self.client.post(reverse('register'), {
            'username': 'second',
            'email': 'taken@test.com',
            'password1': 'securepass123!',
            'password2': 'securepass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            CustomUser.objects.filter(username='second').exists()
        )

    def test_registration_empty_email_fails(self):
        response = self.client.post(reverse('register'), {
            'username': 'noemail',
            'email': '',
            'password1': 'securepass123!',
            'password2': 'securepass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            CustomUser.objects.filter(username='noemail').exists()
        )

    def test_authenticated_user_redirects_away_from_register(self):
        """Already logged-in users should be redirected to dashboard."""
        user = CustomUser.objects.create_user(
            username='loggedin', password='pass123!', role='creator'
        )
        self.client.login(username='loggedin', password='pass123!')
        response = self.client.get(reverse('register'))
        self.assertRedirects(response, reverse('dashboard'))