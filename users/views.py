"""
Authentication views for login, logout, password reset, and registration.

After login or registration, users are redirected to /dashboard/ where
the content app renders the appropriate view based on their role.
"""

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from users.forms import SystemLoginForm, CreatorRegistrationForm


# LOGIN / LOGOUT


class SystemLoginView(auth_views.LoginView):
    """Login view matching the wireframe design."""
    template_name = 'users/login.html'
    authentication_form = SystemLoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('dashboard')


class SystemLogoutView(auth_views.LogoutView):
    """Log the user out and redirect to the login page."""
    next_page = reverse_lazy('login')



# REGISTRATION

def creator_registration_view(request):
    """
    Handle self-registration for new Creator accounts.

    Only the Creator role is available through self-registration.
    Approver accounts must be created by an admin.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = CreatorRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(
                request,
                f'Welcome, {user.username}! Your Creator account has been '
                f'created. You can now upload content folders.'
            )
            return redirect('dashboard')
    else:
        form = CreatorRegistrationForm()

    return render(request, 'users/register.html', {'form': form})


# PASSWORD RESET FLOW


class SystemPasswordResetView(auth_views.PasswordResetView):
    """
    Step 1: User enters their email address.

    Sends a password reset email with a unique link.
    Uses console email backend in development (check terminal output).
    """
    template_name = 'users/password_reset.html'
    email_template_name = 'users/password_reset_email.html'
    subject_template_name = 'users/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

    def form_valid(self, form):
        """Add a helpful message after submitting the form."""
        messages.info(
            self.request,
            'If an account exists with that email, a reset link has been sent. '
            'Check your email (or terminal in development mode).'
        )
        return super().form_valid(form)


class SystemPasswordResetDoneView(auth_views.PasswordResetDoneView):
    """
    Step 2: Confirmation that the email has been sent.
    """
    template_name = 'users/password_reset_done.html'


class SystemPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    """
    Step 3: User clicks the link from email and enters a new password.

    Django handles token validation internally:
    - First visit: validates the real token from the email URL
    - Redirects to /<uidb64>/set-password/ (token stored in session)
    - User submits new password on the redirected page
    """
    template_name = 'users/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')

    def form_valid(self, form):
        """Save the new password and add a success message."""
        messages.success(
            self.request,
            'Your password has been successfully reset! '
            'You can now log in with your new password.'
        )
        return super().form_valid(form)


def password_reset_complete_view(request):
    """
    Step 4: Password has been reset — redirect straight to login.

    Instead of showing a separate "complete" page, we redirect
    directly to the login page. The success message was already
    added in Step 3.
    """
    # Add message in case it wasn't set in Step 3 (e.g., direct URL visit)
    if not any(m.level_tag == 'success' for m in messages.get_messages(request)):
        messages.success(
            request,
            'Your password has been reset. Please log in with your new password.'
        )
    return redirect('login')