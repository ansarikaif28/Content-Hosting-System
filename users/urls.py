"""URL routing for authentication and registration views."""

from django.urls import path
from users import views
from django.views.defaults import permission_denied, page_not_found, server_error



urlpatterns = [
    path(
        'login/',
        views.SystemLoginView.as_view(),
        name='login',
    ),
    path(
        'logout/',
        views.SystemLogoutView.as_view(),
        name='logout',
    ),
    path(
        'register/',
        views.creator_registration_view,
        name='register',
    ),

    # --- Password Reset Flow ---
    # Step 1: Enter email
    path(
        'password-reset/',
        views.SystemPasswordResetView.as_view(),
        name='password_reset',
    ),
    # Step 2: Email sent confirmation
    path(
        'password-reset/done/',
        views.SystemPasswordResetDoneView.as_view(),
        name='password_reset_done',
    ),
    # Step 3: Click link from email → enter new password
    # Django internally redirects from /<uidb64>/<token>/
    # to /<uidb64>/set-password/ after validating the token.
    # The <token> param catches both the real token AND "set-password".
    path(
        'password-reset/confirm/<uidb64>/<token>/',
        views.SystemPasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),
    # Step 4: Success → redirect to login
    path(
        'password-reset/complete/',
        views.password_reset_complete_view,
        name='password_reset_complete',
    ),
]

handler403 = 'django.views.defaults.permission_denied'
handler404 = 'django.views.defaults.page_not_found'
handler500 = 'django.views.defaults.server_error'