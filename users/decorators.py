"""
Role-based access control decorators and mixins.

Usage:
    @role_required('creator')
    def my_view(request):
        ...

    class MyView(RoleRequiredMixin, View):
        required_role = 'creator'
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin


def role_required(required_role):
    """
    Decorator that restricts a view to users with a specific role.

    Args:
        required_role: The role string ('creator' or 'approver').

    Returns:
        Decorated view function that checks login and role.

    Raises:
        PermissionDenied: If the user's role doesn't match.
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped_view(request, *args, **kwargs):
            if request.user.role != required_role:
                raise PermissionDenied(
                    f"This action requires the '{required_role}' role."
                )
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator


class RoleRequiredMixin(LoginRequiredMixin):
    """
    Mixin for class-based views that restricts access by role.

    Set `required_role` on the class:
        class MyView(RoleRequiredMixin, View):
            required_role = 'approver'
    """
    required_role = None

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if (
            request.user.is_authenticated
            and self.required_role
            and request.user.role != self.required_role
        ):
            raise PermissionDenied(
                f"This action requires the '{self.required_role}' role."
            )
        return response