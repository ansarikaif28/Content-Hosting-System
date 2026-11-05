"""URL routing for content management views."""

from django.urls import path
from content import views
from content import htmx_views

urlpatterns = [
    # Dashboard
    path(
        'dashboard/',
        views.dashboard_view,
        name='dashboard',
    ),

    # Upload (renders page + HTMX endpoint for form submission)
    path(
        'upload/',
        views.upload_content_view,
        name='upload',
    ),
    path(
        'upload/htmx/',
        htmx_views.upload_content_htmx_view,
        name='upload_htmx',
    ),

    # Re-upload (renders page + HTMX endpoint for form submission)
    path(
        'upload/<int:pk>/reupload/',
        views.reupload_content_view,
        name='reupload_content',
    ),
    path(
        'upload/<int:pk>/reupload/htmx/',
        htmx_views.reupload_content_htmx_view,
        name='reupload_htmx',
    ),

    # Workflow Actions
    path(
        'upload/<int:pk>/approve/',
        views.approve_upload_view,
        name='approve_upload',
    ),
    path(
        'upload/<int:pk>/reject/',
        views.reject_upload_view,
        name='reject_upload',
    ),
    path(
        'upload/<int:pk>/publish/',
        views.publish_upload_view,
        name='publish_upload',
    ),
    path(
        'upload/<int:pk>/unpublish/',
        views.unpublish_upload_view,
        name='unpublish_upload',
    ),
    path(
        'upload/<int:pk>/delete/',
        views.delete_upload_view,
        name='delete_upload',
    ),
    path(
        'upload/<int:pk>/restore/',
        views.restore_upload_view,
        name='restore_upload',
    ),

    # Content Serving
    path(
        'test/<str:hash_value>/<path:file_path>',
        views.serve_test_content,
        name='serve_test',
    ),
    path(
        'production/<str:hash_value>/<path:file_path>',
        views.serve_production_content,
        name='serve_production',
    ),
]