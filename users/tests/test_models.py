"""Tests for the CustomUser model."""

from django.test import TestCase
from django.contrib.auth.models import Group

from users.models import CustomUser


class CustomUserModelTests(TestCase):
    """Verify CustomUser creation, properties, and group assignment."""

    def test_create_creator_user(self):
        """A user created with role='creator' should have is_creator=True."""
        user = CustomUser.objects.create_user(
            username='alice', password='pass123!', role='creator'
        )
        self.assertEqual(user.role, 'creator')
        self.assertTrue(user.is_creator)
        self.assertFalse(user.is_approver)

    def test_create_approver_user(self):
        """A user created with role='approver' should have is_approver=True."""
        user = CustomUser.objects.create_user(
            username='bob', password='pass123!', role='approver'
        )
        self.assertEqual(user.role, 'approver')
        self.assertTrue(user.is_approver)
        self.assertFalse(user.is_creator)

    def test_user_string_representation(self):
        """__str__ should show username and role display name."""
        user = CustomUser.objects.create_user(
            username='charlie', password='pass123!', role='creator'
        )
        self.assertEqual(str(user), 'charlie (Creator)')

    def test_default_role_is_creator(self):
        """Without explicit role, user should default to 'creator'."""
        user = CustomUser.objects.create_user(
            username='dave', password='pass123!'
        )
        self.assertEqual(user.role, 'creator')

    def test_group_auto_assignment_on_save(self):
        """Saving a user should add them to the matching Django Group."""
        user = CustomUser.objects.create_user(
            username='eve', password='pass123!', role='creator'
        )
        self.assertTrue(
            user.groups.filter(name='Creator').exists()
        )
        self.assertFalse(
            user.groups.filter(name='Approver').exists()
        )

    def test_group_changes_on_role_update(self):
        """Changing a user's role should update their group membership."""
        user = CustomUser.objects.create_user(
            username='frank', password='pass123!', role='creator'
        )
        user.role = 'approver'
        user.save()
        self.assertTrue(user.groups.filter(name='Approver').exists())
        self.assertFalse(user.groups.filter(name='Creator').exists())