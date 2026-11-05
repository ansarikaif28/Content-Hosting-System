"""Authentication and registration forms for the Content Hosting System."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm

from users.models import CustomUser


class SystemLoginForm(AuthenticationForm):
    """
    Custom login form matching the wireframe design.
    """
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your username',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password',
        })
    )


class CreatorRegistrationForm(forms.ModelForm):
    """
    Registration form for new Creator accounts.

    Only the Creator role can self-register. Approver accounts
    must be created by an administrator through the Django admin.
    """

    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create a password',
        }),
        help_text='Must be at least 8 characters.',
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Repeat your password',
        }),
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Choose a username',
                'autofocus': True,
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'your.email@example.com',
            }),
        }

    def clean_email(self):
        """Ensure email is provided and unique."""
        email = self.cleaned_data.get('email', '').strip()
        if not email:
            raise forms.ValidationError('Email address is required.')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError(
                'An account with this email already exists.'
            )
        return email

    def clean_password2(self):
        """Verify that both passwords match."""
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Passwords do not match.')
        return password2

    def clean_password1(self):
        """Basic password strength validation."""
        password = self.cleaned_data.get('password1', '')
        if len(password) < 8:
            raise forms.ValidationError(
                'Password must be at least 8 characters long.'
            )
        return password

    def save(self, commit=True):
        """
        Create the user with Creator role.

        The role is hardcoded to 'creator' — users cannot
        self-register as approvers.
        """
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.role = CustomUser.ROLE_CREATOR  # Always Creator
        if commit:
            user.save()
        return user