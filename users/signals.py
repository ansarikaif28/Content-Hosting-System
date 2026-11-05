"""
Signals to auto-assign users to Django Groups based on their role.

When a CustomUser is saved, this signal ensures they belong to the
correct Group (Creator or Approver) and removes them from the other Group.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import Group

from users.models import CustomUser


@receiver(post_save, sender=CustomUser)
def assign_user_to_role_group(sender, instance, created, **kwargs):
    """
    Assign the user to the Django Group matching their role.

    Ensures each user is in exactly one role group. Creates the
    group if it doesn't already exist.
    """
    creator_group, _ = Group.objects.get_or_create(name='Creator')
    approver_group, _ = Group.objects.get_or_create(name='Approver')

    if instance.role == CustomUser.ROLE_CREATOR:
        creator_group.user_set.add(instance)
        approver_group.user_set.remove(instance)
    elif instance.role == CustomUser.ROLE_APPROVER:
        approver_group.user_set.add(instance)
        creator_group.user_set.remove(instance)