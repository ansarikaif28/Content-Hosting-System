"""
Core views for the content hosting system.

Handles dashboards, initial upload page rendering, approval workflow, 
content serving, and all state transitions in the content pipeline.

View Index:
    - dashboard_view              → Role-based dashboard router
    - upload_content_view         → Renders Creator folder upload page (POST handled by HTMX)
    - reupload_content_view       → Renders Creator re-upload page (POST handled by HTMX)
    - approve_upload_view         → Approver approves (or re-approves) upload
    - reject_upload_view          → Approver rejects upload (with reason)
    - publish_upload_view         → Approver publishes to production
    - unpublish_upload_view       → Approver removes from production (with reason)
    - delete_upload_view          → Soft-delete (Creator own / Approver any)
    - restore_upload_view         → Restore deleted upload (Creator own / Approver any)
    - serve_test_content          → Serve test files (login required)
    - serve_production_content    → Serve production files (public)

"""

import re
import shutil
import mimetypes
import tempfile
import logging
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import (
    FileResponse, Http404, HttpResponseForbidden,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from audit.services import get_state_snapshot, log_action
from audit.models import ActionLog
from content.constants import (
    STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED,
    STATUS_PUBLISHED, STATUS_UNPUBLISHED, STATUS_DELETED,
    ACTION_UPLOAD_APPROVED, ACTION_UPLOAD_REJECTED, 
    ACTION_UPLOAD_PUBLISHED, ACTION_UPLOAD_UNPUBLISHED, 
    ACTION_UPLOAD_DELETED, ACTION_UPLOAD_RESTORED,
    ENV_TEST, ENV_PRODUCTION,
)
from content.models import UploadHistory, LiveState
from content.utils.filesystem import (
    deploy_to_test, deploy_to_production,
    undeploy_from_test, undeploy_from_production,
    move_to_deleted, restore_from_deleted,
    ArchiveNotFoundError,
)
from users.decorators import role_required

logger = logging.getLogger(__name__)

# Regex for validating SHA-256 hash format (exactly 64 hex characters)
HASH_PATTERN = re.compile(r'^[a-f0-9]{64}$')


# UPLOAD HELPER — Used by htmx_views.py

def _reconstruct_uploaded_folder(request, folder_name: str) -> tuple[Path, Path, list]:
    """
    Reconstruct the folder structure from uploaded files.

    Django strips directory paths from uploaded filenames for security.
    To preserve the structure, the frontend sends the original relative
    paths as separate 'file_paths' text fields alongside the actual files.
    """
    uploaded_files = request.FILES.getlist('folder_files')
    file_paths = request.POST.getlist('file_paths')

    errors = []

    if not uploaded_files:
        errors.append('No files were uploaded.')
        return None, None, errors

    temp_dir = Path(tempfile.mkdtemp(prefix='upload_'))
    content_root = temp_dir / folder_name

    for i, uploaded_file in enumerate(uploaded_files):
        if i < len(file_paths) and file_paths[i]:
            raw_path = file_paths[i].replace('\\', '/')
        else:
            raw_path = (uploaded_file.name or '').replace('\\', '/')

        raw_path = raw_path.strip('/')
        parts = [p for p in raw_path.split('/') if p]

        relative_path = ''

        known_roots = ['en', 'de', 'shared-assets']
        for idx in range(len(parts)):
            if parts[idx] in known_roots:
                relative_path = '/'.join(parts[idx:])
                break

        if not relative_path:
            if len(parts) > 1:
                relative_path = '/'.join(parts[1:])
            elif parts:
                relative_path = parts[0]

        if not relative_path or relative_path.strip() == '':
            continue

        if '..' in relative_path:
            errors.append(f'Path traversal detected: {relative_path}')
            continue

        target_path = content_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(target_path, 'wb') as dest:
                for chunk in uploaded_file.chunks():
                    dest.write(chunk)
        except Exception as e:
            errors.append(f'Failed to write {relative_path}: {str(e)}')

    if errors:
        return temp_dir, content_root, errors

    return temp_dir, content_root, []


# DASHBOARD VIEWS

@login_required
def dashboard_view(request):
    """Render the appropriate dashboard based on the user's role."""
    if request.user.is_approver:
        return _render_approver_dashboard(request)
    return _render_creator_dashboard(request)


def _render_creator_dashboard(request):
    all_uploads = UploadHistory.objects.filter(uploaded_by=request.user)

    search_query = request.GET.get('q', '').strip()
    if search_query:
        all_uploads = all_uploads.filter(folder_name__icontains=search_query)

    sort_field = request.GET.get('sort', '-uploaded_at')
    allowed_sort_fields = [
        'folder_name', '-folder_name',
        'uploaded_at', '-uploaded_at',
        'status', '-status',
        'hash_value', '-hash_value',
    ]
    if sort_field in allowed_sort_fields:
        all_uploads = all_uploads.order_by(sort_field)

    context = {
        'uploads': all_uploads,
        'search_query': search_query,
        'current_sort': sort_field,
    }

    template = 'content/creator_dashboard.html'
    if hasattr(request, 'htmx') and request.htmx:
        template = 'content/partials/creator_table.html'

    return render(request, template, context)


def _render_approver_dashboard(request):
    live_states = LiveState.objects.filter(
        environment=ENV_PRODUCTION
    ).select_related('updated_by', 'source_upload')

    pending_uploads = UploadHistory.objects.filter(status=STATUS_PENDING).select_related('uploaded_by')
    approved_uploads = UploadHistory.objects.filter(status=STATUS_APPROVED).select_related('uploaded_by')
    rejected_uploads = UploadHistory.objects.filter(status=STATUS_REJECTED).select_related('uploaded_by')
    unpublished_uploads = UploadHistory.objects.filter(status=STATUS_UNPUBLISHED).select_related('uploaded_by')
    deleted_uploads = UploadHistory.objects.filter(status=STATUS_DELETED).select_related('uploaded_by', 'deleted_by')

    search_query = request.GET.get('q', '').strip()
    if search_query:
        pending_uploads = pending_uploads.filter(folder_name__icontains=search_query)
        approved_uploads = approved_uploads.filter(folder_name__icontains=search_query)
        rejected_uploads = rejected_uploads.filter(folder_name__icontains=search_query)
        unpublished_uploads = unpublished_uploads.filter(folder_name__icontains=search_query)
        deleted_uploads = deleted_uploads.filter(folder_name__icontains=search_query)

    sort_field = request.GET.get('sort', '-uploaded_at')
    allowed_sort_fields = [
        'folder_name', '-folder_name',
        'uploaded_at', '-uploaded_at',
        'hash_value', '-hash_value',
    ]
    if sort_field in allowed_sort_fields:
        pending_uploads = pending_uploads.order_by(sort_field)
        approved_uploads = approved_uploads.order_by(sort_field)
        rejected_uploads = rejected_uploads.order_by(sort_field)
        unpublished_uploads = unpublished_uploads.order_by(sort_field)
        deleted_uploads = deleted_uploads.order_by(sort_field)

    context = {
        'live_states': live_states,
        'pending_uploads': pending_uploads,
        'approved_uploads': approved_uploads,
        'rejected_uploads': rejected_uploads,
        'unpublished_uploads': unpublished_uploads,
        'deleted_uploads': deleted_uploads,
        'search_query': search_query,
        'current_sort': sort_field,
        'now': timezone.now(),
    }

    template = 'content/approver_dashboard.html'
    if hasattr(request, 'htmx') and request.htmx:
        template = 'content/partials/approver_tables.html'

    return render(request, template, context)


# PAGE RENDERING VIEWS (POST handled by HTMX)

@role_required('creator')
def upload_content_view(request):
    """
    Render the empty upload page.
    Form submission is intercepted and processed by htmx_views.py
    """
    return render(request, 'content/upload.html')


@role_required('creator')
def reupload_content_view(request, pk):
    """
    Render the re-upload page for a specific upload.
    Form submission is intercepted and processed by htmx_views.py
    """
    original_upload = get_object_or_404(UploadHistory, pk=pk)

    if original_upload.uploaded_by != request.user:
        return HttpResponseForbidden('You can only re-upload your own content.')

    allowed_statuses = [STATUS_REJECTED, STATUS_UNPUBLISHED]
    if original_upload.status not in allowed_statuses:
        messages.error(
            request,
            f'Cannot re-upload: upload is currently {original_upload.get_status_display()}. '
            f'Only rejected or unpublished uploads can be re-uploaded.'
        )
        return redirect('dashboard')

    # Fetch the rejection/unpublish reason from the audit log
    reason_entry = ActionLog.objects.filter(
        entity_type='upload',
        entity_id=original_upload.id,
        action_type__in=[ACTION_UPLOAD_REJECTED, ACTION_UPLOAD_UNPUBLISHED],
    ).order_by('-timestamp').first()

    reason = reason_entry.details.get('reason', '') if reason_entry and reason_entry.details else ''

    return render(request, 'content/reupload.html', {
        'original_upload': original_upload,
        'reason': reason,
    })


# APPROVAL WORKFLOW VIEWS

@require_POST
@role_required('approver')
def approve_upload_view(request, pk):
    upload = get_object_or_404(UploadHistory, pk=pk)

    allowed_statuses = [STATUS_PENDING, STATUS_REJECTED, STATUS_UNPUBLISHED]
    if upload.status not in allowed_statuses:
        messages.error(request, f'Cannot approve: upload is currently {upload.get_status_display()}.')
        return redirect('dashboard')

    old_state = get_state_snapshot(upload)
    previous_status = upload.status

    if upload.status == STATUS_REJECTED:
        try:
            test_path = deploy_to_test(upload.hash_value)
            LiveState.objects.update_or_create(
                environment=ENV_TEST,
                current_hash=upload.hash_value,
                defaults={
                    'folder_name': upload.folder_name,
                    'working_path': str(test_path),
                    'source_upload': upload,
                    'updated_by': request.user,
                },
            )
        except ArchiveNotFoundError as e:
            messages.error(request, str(e))
            return redirect('dashboard')

    upload.status = STATUS_APPROVED
    upload.save()

    new_state = get_state_snapshot(upload)

    log_action(
        actor=request.user,
        action_type=ACTION_UPLOAD_APPROVED,
        entity_type='upload',
        entity_id=upload.id,
        related_hash=upload.hash_value,
        old_state=old_state,
        new_state=new_state,
        details={'previous_status': previous_status, 'note': request.POST.get('note', '')},
        request=request,
    )

    action_word = 're-approved' if previous_status in [STATUS_REJECTED, STATUS_UNPUBLISHED] else 'approved'
    messages.success(request, f'"{upload.folder_name}" has been {action_word} and is ready for publishing.')
    return redirect('dashboard')


@require_POST
@role_required('approver')
def reject_upload_view(request, pk):
    upload = get_object_or_404(UploadHistory, pk=pk)

    if upload.status != STATUS_PENDING:
        messages.error(request, f'Cannot reject: upload is currently {upload.get_status_display()}.')
        return redirect('dashboard')

    reason = request.POST.get('reason', '').strip()
    if not reason:
        messages.error(request, 'Please provide a reason for rejection so the creator knows what to fix.')
        return redirect('dashboard')

    old_state = get_state_snapshot(upload)

    undeploy_from_test(upload.hash_value)
    LiveState.objects.filter(environment=ENV_TEST, current_hash=upload.hash_value).delete()

    upload.status = STATUS_REJECTED
    upload.save()

    new_state = get_state_snapshot(upload)

    log_action(
        actor=request.user,
        action_type=ACTION_UPLOAD_REJECTED,
        entity_type='upload',
        entity_id=upload.id,
        related_hash=upload.hash_value,
        old_state=old_state,
        new_state=new_state,
        details={'reason': reason},
        request=request,
    )

    messages.success(request, f'"{upload.folder_name}" has been rejected. The creator will see your feedback.')
    return redirect('dashboard')


@require_POST
@role_required('approver')
def publish_upload_view(request, pk):
    upload = get_object_or_404(UploadHistory, pk=pk)

    if upload.status != STATUS_APPROVED:
        messages.error(request, f'Cannot publish: upload must be approved first (currently {upload.get_status_display()}).')
        return redirect('dashboard')

    old_state = get_state_snapshot(upload)

    try:
        production_path = deploy_to_production(upload.hash_value)

        undeploy_from_test(upload.hash_value)
        LiveState.objects.filter(environment=ENV_TEST, current_hash=upload.hash_value).delete()

        LiveState.objects.update_or_create(
            environment=ENV_PRODUCTION,
            current_hash=upload.hash_value,
            defaults={
                'folder_name': upload.folder_name,
                'working_path': str(production_path),
                'source_upload': upload,
                'updated_by': request.user,
            },
        )

        upload.status = STATUS_PUBLISHED
        upload.save()

        new_state = get_state_snapshot(upload)

        log_action(
            actor=request.user,
            action_type=ACTION_UPLOAD_PUBLISHED,
            entity_type='upload',
            entity_id=upload.id,
            related_hash=upload.hash_value,
            old_state=old_state,
            new_state=new_state,
            request=request,
        )

        messages.success(request, f'"{upload.folder_name}" is now live in production! Available in EN and DE.')

    except ArchiveNotFoundError as e:
        messages.error(request, str(e))

    return redirect('dashboard')


@require_POST
@role_required('approver')
def unpublish_upload_view(request, pk):
    upload = get_object_or_404(UploadHistory, pk=pk)

    if upload.status != STATUS_PUBLISHED:
        messages.error(request, f'Cannot unpublish: upload is currently {upload.get_status_display()}.')
        return redirect('dashboard')

    reason = request.POST.get('reason', '').strip()
    old_state = get_state_snapshot(upload)

    try:
        undeploy_from_production(upload.hash_value)
        LiveState.objects.filter(environment=ENV_PRODUCTION, current_hash=upload.hash_value).delete()

        test_path = deploy_to_test(upload.hash_value)
        LiveState.objects.update_or_create(
            environment=ENV_TEST,
            current_hash=upload.hash_value,
            defaults={
                'folder_name': upload.folder_name,
                'working_path': str(test_path),
                'source_upload': upload,
                'updated_by': request.user,
            },
        )

        upload.status = STATUS_UNPUBLISHED
        upload.save()

        new_state = get_state_snapshot(upload)

        log_action(
            actor=request.user,
            action_type=ACTION_UPLOAD_UNPUBLISHED,
            entity_type='upload',
            entity_id=upload.id,
            related_hash=upload.hash_value,
            old_state=old_state,
            new_state=new_state,
            details={'reason': reason},
            request=request,
        )

        messages.success(request, f'"{upload.folder_name}" has been unpublished and moved back to the test environment.')

    except ArchiveNotFoundError as e:
        messages.error(request, str(e))

    return redirect('dashboard')


# DELETE & RESTORE VIEWS

@require_POST
@login_required
def delete_upload_view(request, pk):
    upload = get_object_or_404(UploadHistory, pk=pk)

    if request.user.is_creator and upload.uploaded_by != request.user:
        return HttpResponseForbidden('You can only delete your own uploads.')

    if upload.status == STATUS_DELETED:
        messages.warning(request, 'This upload has already been deleted.')
        return redirect('dashboard')

    old_state = get_state_snapshot(upload)

    move_to_deleted(upload.hash_value)
    LiveState.objects.filter(current_hash=upload.hash_value).delete()

    upload.status = STATUS_DELETED
    upload.deleted_by = request.user
    upload.deleted_at = timezone.now()
    upload.save()

    new_state = get_state_snapshot(upload)

    log_action(
        actor=request.user,
        action_type=ACTION_UPLOAD_DELETED,
        entity_type='upload',
        entity_id=upload.id,
        related_hash=upload.hash_value,
        old_state=old_state,
        new_state=new_state,
        details={'deleted_by_role': 'approver' if request.user.is_approver else 'creator'},
        request=request,
    )

    restore_msg = 'It can be restored by an approver.' if request.user.is_approver else 'You can restore it from your dashboard.'
    messages.success(request, f'"{upload.folder_name}" has been deleted. {restore_msg}')
    return redirect('dashboard')


@require_POST
@login_required
def restore_upload_view(request, pk):
    upload = get_object_or_404(UploadHistory, pk=pk)

    if upload.status != STATUS_DELETED:
        messages.error(request, f'Cannot restore: upload is currently {upload.get_status_display()}.')
        return redirect('dashboard')

    deleted_by_approver = upload.deleted_by is not None and upload.deleted_by.is_approver

    if request.user.is_creator:
        if upload.uploaded_by != request.user:
            return HttpResponseForbidden('You can only restore your own uploads.')
        if deleted_by_approver:
            messages.error(request, f'"{upload.folder_name}" was deleted by an approver. Please upload a new version instead.')
            return redirect('dashboard')

    old_state = get_state_snapshot(upload)

    try:
        test_path = restore_from_deleted(upload.hash_value)

        LiveState.objects.update_or_create(
            environment=ENV_TEST,
            current_hash=upload.hash_value,
            defaults={
                'folder_name': upload.folder_name,
                'working_path': str(test_path),
                'source_upload': upload,
                'updated_by': request.user,
            },
        )

        upload.status = STATUS_PENDING
        upload.deleted_by = None
        upload.deleted_at = None
        upload.save()

        new_state = get_state_snapshot(upload)

        log_action(
            actor=request.user,
            action_type=ACTION_UPLOAD_RESTORED,
            entity_type='upload',
            entity_id=upload.id,
            related_hash=upload.hash_value,
            old_state=old_state,
            new_state=new_state,
            details={'restored_by_role': 'approver' if request.user.is_approver else 'creator'},
            request=request,
        )

        messages.success(request, f'"{upload.folder_name}" has been restored and is pending review again.')

    except ArchiveNotFoundError as e:
        messages.error(request, f'Cannot restore: {str(e)} The archive may have been pruned.')

    return redirect('dashboard')


# CONTENT SERVING VIEWS

def _validate_content_path(hash_value: str, file_path: str) -> bool:
    if not HASH_PATTERN.match(hash_value):
        return False
    if '..' in file_path or '\x00' in file_path or '\\' in file_path:
        return False
    return True


def _serve_content_file(base_dir: str, hash_value: str, file_path: str):
    if not _validate_content_path(hash_value, file_path):
        raise Http404("Invalid content path.")

    full_path = Path(settings.WORKING_DIR) / base_dir / hash_value / file_path

    if not full_path.exists() or not full_path.is_file():
        raise Http404("Content not found.")

    try:
        full_path.resolve().relative_to((Path(settings.WORKING_DIR) / base_dir).resolve())
    except ValueError:
        raise Http404("Invalid content path.")

    content_type, _ = mimetypes.guess_type(str(full_path))
    response = FileResponse(open(full_path, 'rb'), content_type=content_type or 'application/octet-stream')
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
def serve_test_content(request, hash_value, file_path):
    from content.models import LiveState
    from content.constants import ENV_TEST

    if not _validate_content_path(hash_value, file_path):
        lang_codes = ['en', 'de']
        if hash_value in lang_codes and file_path.endswith('index.html'):
            referrer = request.META.get('HTTP_REFERER', '')
            import re
            hash_match = re.search(r'/test/([a-f0-9]{64})/', referrer)
            if hash_match:
                original_hash = hash_match.group(1)
                correct_path = f"{hash_value}/index.html"
                correct_url = f"/test/{original_hash}/{correct_path}"
                return redirect(correct_url, permanent=True)
            try:
                from content.constants import STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED, STATUS_UNPUBLISHED
                live_state = LiveState.objects.filter(environment=ENV_TEST, source_upload__status__in=[STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED, STATUS_UNPUBLISHED]).latest('last_updated')
                correct_path = f"{hash_value}/index.html"
                correct_url = request.build_absolute_uri(f"/test/{live_state.current_hash}/{correct_path}")
                return redirect(correct_url, permanent=True)
            except Exception:
                pass

    return _serve_content_file('test', hash_value, file_path)


def serve_production_content(request, hash_value, file_path):
    from content.models import LiveState
    from content.constants import ENV_PRODUCTION

    if not _validate_content_path(hash_value, file_path):
        lang_codes = ['en', 'de']
        if hash_value in lang_codes and file_path.endswith('index.html'):
            referrer = request.META.get('HTTP_REFERER', '')
            import re
            hash_match = re.search(r'/production/([a-f0-9]{64})/', referrer)
            if hash_match:
                original_hash = hash_match.group(1)
                correct_path = f"{hash_value}/index.html"
                correct_url = f"/production/{original_hash}/{correct_path}"
                return redirect(correct_url, permanent=True)
            try:
                from content.constants import STATUS_PUBLISHED
                live_state = LiveState.objects.filter(environment=ENV_PRODUCTION, source_upload__status=STATUS_PUBLISHED).latest('last_updated')
                correct_path = f"{hash_value}/index.html"
                correct_url = request.build_absolute_uri(f"/production/{live_state.current_hash}/{correct_path}")
                return redirect(correct_url, permanent=True)
            except Exception:
                pass

    return _serve_content_file('production', hash_value, file_path)