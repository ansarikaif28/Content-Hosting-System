"""
HTMX-driven views for the content hosting system.

This module handles the `webkitdirectory` folder uploads using HTMX.
Instead of returning JSON or full page reloads, these endpoints process the 
upload process and return small, targeted HTML fragments.

"""
import shutil
import logging
from pathlib import Path

from django.conf import settings
from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.http import require_POST

from content.constants import (
    STATUS_PENDING, STATUS_REJECTED, STATUS_UNPUBLISHED, STATUS_DELETED,
    ENV_TEST, ACTION_UPLOAD_CREATED, ACTION_UPLOAD_REUPLOADED, ACTION_UPLOAD_DELETED,
)
from content.models import UploadHistory, LiveState
from content.utils.filesystem import (
    archive_upload, deploy_to_test, undeploy_from_test,
    count_files_in_directory, calculate_directory_size, DuplicateUploadError,
)
from content.utils.hashing import generate_content_hash
from content.utils.validators import (
    validate_folder_structure, validate_file_safety, validate_folder_name,
)
from audit.services import log_action, get_state_snapshot
from users.decorators import role_required
from content.views import _reconstruct_uploaded_folder

logger = logging.getLogger(__name__)

def _get_base_steps(is_reupload=False):
    """Returns the ordered list of processing steps."""
    steps = []
    if is_reupload:
        steps.append({'id': 'validate_ownership', 'label': 'Validate Ownership', 'status': 'skip', 'message': ''})
        
    steps.extend([
        {'id': 'validate_structure', 'label': 'Validate Folder Structure', 'status': 'skip', 'message': ''},
        {'id': 'validate_safety', 'label': 'Security & File Safety Check', 'status': 'skip', 'message': ''},
        {'id': 'generate_hash', 'label': 'Generate SHA-256 Hash', 'status': 'skip', 'message': ''},
        {'id': 'archive', 'label': 'Archive to Vault', 'status': 'skip', 'message': ''},
        {'id': 'deploy_test', 'label': 'Deploy to Test Environment', 'status': 'skip', 'message': ''},
        {'id': 'create_records', 'label': 'Create Database Records', 'status': 'skip', 'message': ''},
    ])
    
    if is_reupload:
        steps.append({'id': 'cleanup_old', 'label': 'Cleanup Previous Version', 'status': 'skip', 'message': ''})
        
    steps.append({'id': 'log_action', 'label': 'Log Action to Audit Trail', 'status': 'skip', 'message': ''})
    return steps


def _update_step(steps, step_id, status, message):
    """Helper to update a step's status in the list."""
    for step in steps:
        if step['id'] == step_id:
            step['status'] = status
            step['message'] = message
            break


def _render_fragment(request, steps, success, **kwargs):
    """Calculates animation delays and renders the fragment."""
    delay = 0
    for step in steps:
        step['delay'] = delay
        delay += 300  # 300ms gap between each step appearing

    context = {
        'steps': steps,
        'success': success,
        'final_delay': delay + 200,
        'redirect_url': '/dashboard/'
    }
    context.update(kwargs)
    return render(request, 'content/partials/upload_progress_fragment.html', context)


@role_required('creator')
@require_POST
def upload_content_htmx_view(request):
    logger.info(f"Upload HTMX called by {request.user}.")
    steps = _get_base_steps(is_reupload=False)
    
    # 1. Bypass the broken form validation and pull data directly!
    folder_name = request.POST.get('folder_name', '').strip()
    folder_files = request.FILES.getlist('folder_files')
    file_paths = request.POST.getlist('file_paths')

    if not folder_name:
        return _render_fragment(request, steps, False, error="Folder name is required.")
        
    if not folder_files or not file_paths:
        return _render_fragment(request, steps, False, error="No files were submitted. Please select a folder.")

    temp_dir = None
    try:
        # Step 1: Structure
        is_valid_name, name_error = validate_folder_name(folder_name)
        if not is_valid_name:
            _update_step(steps, 'validate_structure', 'fail', name_error)
            return _render_fragment(request, steps, False, error=name_error)

        temp_dir, content_root, reconstruct_errors = _reconstruct_uploaded_folder(request, folder_name)
        if reconstruct_errors:
            _update_step(steps, 'validate_structure', 'fail', '; '.join(reconstruct_errors))
            return _render_fragment(request, steps, False, error="Failed to reconstruct folder.")

        is_valid_structure, structure_errors = validate_folder_structure(content_root)
        if not is_valid_structure:
            _update_step(steps, 'validate_structure', 'fail', '; '.join(structure_errors))
            return _render_fragment(request, steps, False, error="Folder structure invalid.")
        _update_step(steps, 'validate_structure', 'pass', 'Structure valid.')

        # Step 2: Safety
        is_safe, safety_errors = validate_file_safety(content_root)
        if not is_safe:
            _update_step(steps, 'validate_safety', 'fail', '; '.join(safety_errors))
            return _render_fragment(request, steps, False, error="Security check failed.")
        _update_step(steps, 'validate_safety', 'pass', 'All files safe.')

        # Step 3: Hash
        hash_value = generate_content_hash(content_root)
        _update_step(steps, 'generate_hash', 'pass', f"Hash: {hash_value[:16]}...")

        # Step 4: Archive
        try:
            archive_path = archive_upload(content_root, hash_value)
            _update_step(steps, 'archive', 'pass', 'Saved to vault.')
        except DuplicateUploadError:
            _update_step(steps, 'archive', 'fail', 'Duplicate content detected.')
            return _render_fragment(request, steps, False, error="This exact content has already been uploaded.")

        # Step 5: Deploy
        test_path = deploy_to_test(hash_value)
        _update_step(steps, 'deploy_test', 'pass', 'Deployed to Test.')

        # Step 6: Records
        file_count = count_files_in_directory(archive_path)
        total_size = calculate_directory_size(archive_path)
        upload_obj = UploadHistory.objects.create(
            folder_name=folder_name, hash_value=hash_value, archive_path=str(archive_path),
            status=STATUS_PENDING, uploaded_by=request.user, file_count=file_count, total_size=total_size
        )
        LiveState.objects.create(
            environment=ENV_TEST, folder_name=folder_name, current_hash=hash_value,
            working_path=str(test_path), source_upload=upload_obj, updated_by=request.user
        )
        _update_step(steps, 'create_records', 'pass', f'{file_count} files tracked.')

        # Step 7: Log
        log_action(actor=request.user, action_type=ACTION_UPLOAD_CREATED, entity_type='upload',
                   entity_id=upload_obj.id, related_hash=hash_value, old_state=None,
                   new_state=get_state_snapshot(upload_obj), details={'folder_name': folder_name}, request=request)
        _update_step(steps, 'log_action', 'pass', 'Logged to audit trail.')

        return _render_fragment(request, steps, True, message=f'"{folder_name}" is ready for preview.')

    except Exception as e:
        logger.exception("Upload failed")
        return _render_fragment(request, steps, False, error=f"System error: {str(e)}")
    finally:
        if temp_dir and isinstance(temp_dir, Path) and temp_dir.exists():
            shutil.rmtree(str(temp_dir), ignore_errors=True)


@role_required('creator')
@require_POST
def reupload_content_htmx_view(request, pk):
    logger.info(f"Reupload HTMX called by {request.user} for pk={pk}.")
    steps = _get_base_steps(is_reupload=True)
    temp_dir = None
    
    try:
        original_upload = UploadHistory.objects.get(pk=pk)
    except UploadHistory.DoesNotExist:
        _update_step(steps, 'validate_ownership', 'fail', 'Original upload not found.')
        return _render_fragment(request, steps, False, error="Original upload not found.")

    if original_upload.uploaded_by != request.user:
        _update_step(steps, 'validate_ownership', 'fail', 'Permission denied.')
        return _render_fragment(request, steps, False, error="You can only re-upload your own content.")

    if original_upload.status not in [STATUS_REJECTED, STATUS_UNPUBLISHED]:
        _update_step(steps, 'validate_ownership', 'fail', 'Invalid status.')
        return _render_fragment(request, steps, False, error="Cannot re-upload this status.")
    
    _update_step(steps, 'validate_ownership', 'pass', 'Verified ownership and status.')

    # 1. Bypass the broken form validation and pull data directly!
    folder_name = request.POST.get('folder_name', '').strip() or original_upload.folder_name
    folder_files = request.FILES.getlist('folder_files')
    file_paths = request.POST.getlist('file_paths')

    if not folder_files or not file_paths:
        return _render_fragment(request, steps, False, error="No files were submitted. Please select a folder.")

    try:
        temp_dir, content_root, reconstruct_errors = _reconstruct_uploaded_folder(request, folder_name)
        if reconstruct_errors:
            _update_step(steps, 'validate_structure', 'fail', 'Failed to read files.')
            return _render_fragment(request, steps, False, error="Failed to reconstruct folder.")

        is_valid_structure, structure_errors = validate_folder_structure(content_root)
        if not is_valid_structure:
            _update_step(steps, 'validate_structure', 'fail', '; '.join(structure_errors))
            return _render_fragment(request, steps, False, error="Structure validation failed.")
        _update_step(steps, 'validate_structure', 'pass', 'Structure valid.')

        is_safe, safety_errors = validate_file_safety(content_root)
        if not is_safe:
            _update_step(steps, 'validate_safety', 'fail', '; '.join(safety_errors))
            return _render_fragment(request, steps, False, error="Security check failed.")
        _update_step(steps, 'validate_safety', 'pass', 'All files safe.')

        hash_value = generate_content_hash(content_root)
        if hash_value == original_upload.hash_value:
            _update_step(steps, 'generate_hash', 'fail', 'Duplicate hash.')
            return _render_fragment(request, steps, False, error="Identical to the original content.")
        _update_step(steps, 'generate_hash', 'pass', f"Hash: {hash_value[:16]}...")

        try:
            archive_path = archive_upload(content_root, hash_value)
            _update_step(steps, 'archive', 'pass', 'Saved to vault.')
        except DuplicateUploadError:
            _update_step(steps, 'archive', 'fail', 'Duplicate detected.')
            return _render_fragment(request, steps, False, error="Hash already exists in the system.")

        test_path = deploy_to_test(hash_value)
        _update_step(steps, 'deploy_test', 'pass', 'Deployed to Test.')

        file_count = count_files_in_directory(archive_path)
        total_size = calculate_directory_size(archive_path)
        new_upload = UploadHistory.objects.create(
            folder_name=folder_name, hash_value=hash_value, archive_path=str(archive_path),
            status=STATUS_PENDING, uploaded_by=request.user, file_count=file_count,
            total_size=total_size, replaces=original_upload
        )
        LiveState.objects.create(
            environment=ENV_TEST, folder_name=folder_name, current_hash=hash_value,
            working_path=str(test_path), source_upload=new_upload, updated_by=request.user
        )
        _update_step(steps, 'create_records', 'pass', f'{file_count} files tracked.')

        # Cleanup old
        old_state = get_state_snapshot(original_upload)
        undeploy_from_test(original_upload.hash_value)
        LiveState.objects.filter(current_hash=original_upload.hash_value).delete()
        original_upload.status = STATUS_DELETED
        original_upload.save()
        _update_step(steps, 'cleanup_old', 'pass', 'Previous version archived.')

        # Log
        log_action(actor=request.user, action_type=ACTION_UPLOAD_REUPLOADED, entity_type='upload',
                   entity_id=new_upload.id, related_hash=hash_value, old_state=old_state,
                   new_state=get_state_snapshot(new_upload), details={'folder_name': folder_name}, request=request)
        _update_step(steps, 'log_action', 'pass', 'Logged to audit trail.')

        return _render_fragment(request, steps, True, message='Successfully re-uploaded.')

    except Exception as e:
        logger.exception("Reupload failed")
        return _render_fragment(request, steps, False, error=f"System error: {str(e)}")
    finally:
        if temp_dir and isinstance(temp_dir, Path) and temp_dir.exists():
            shutil.rmtree(str(temp_dir), ignore_errors=True)