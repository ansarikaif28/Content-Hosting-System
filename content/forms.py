"""
Forms for content upload and validation.

The folder upload uses the HTML5 `webkitdirectory` attribute to allow
users to select an entire folder. The individual files are reconstructed
into the proper directory structure on the server.
"""

from django import forms

from content.utils.validators import validate_folder_name


class MultipleFileInput(forms.FileInput):
    """
    Custom file input widget that supports the `multiple` attribute
    and the `webkitdirectory` attribute for folder uploads.
    """
    allow_multiple_selected = True

    def __init__(self, attrs=None):
        super().__init__(attrs)

    def value_from_datadict(self, data, files, name):
        """Return a list of files instead of a single file."""
        if hasattr(files, 'getlist'):
            return files.getlist(name)
        return files.get(name)


class FolderUploadForm(forms.Form):
    """
    Form for uploading a content folder.

    The `folder_files` field accepts multiple files selected via the
    `webkitdirectory` attribute. The `folder_name` field provides a
    human-readable identifier.
    """

    folder_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Product_Page_v2',
        }),
        help_text='Letters, digits, hyphens, and underscores only.',
    )

    folder_files = forms.FileField(
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'webkitdirectory': True,
            'directory': True,
            'multiple': True,
            'id': 'folder-input',
        }),
        required=True,
        help_text='Select a folder containing en/, de/, and shared-assets/ directories.',
    )

    def clean_folder_name(self):
        """Validate the folder name contains only safe characters."""
        name = self.cleaned_data['folder_name']
        is_valid, error_message = validate_folder_name(name)
        if not is_valid:
            raise forms.ValidationError(error_message)
        return name

    def clean_folder_files(self):
        """
        Validate that at least one file was uploaded.

        The actual folder structure validation happens in the view
        after the files are reconstructed into a directory tree.
        """
        files = self.files.getlist('folder_files')
        if not files:
            raise forms.ValidationError('Please select a folder to upload.')
        return files