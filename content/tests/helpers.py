"""
Shared test utilities for creating test fixtures.
"""

from pathlib import Path

from django.test import Client

from users.models import CustomUser


def create_valid_test_folder(
    base_path: Path,
    folder_name: str = 'test-site'
) -> Path:
    """
    Create a folder with the required content structure for testing.

    Structure:
        <folder_name>/
            en/
                index.html
                style.css
            de/
                index.html
                style.css
            shared-assets/
                images/
                    placeholder.txt

    Returns:
        Path to the created root folder.
    """
    root = base_path / folder_name
    root.mkdir(parents=True, exist_ok=True)

    # English content
    en_dir = root / 'en'
    en_dir.mkdir(exist_ok=True)
    (en_dir / 'index.html').write_text(
        '<html><head><title>EN</title></head>'
        '<body><h1>English Page</h1></body></html>'
    )
    (en_dir / 'style.css').write_text(
        'body { font-family: sans-serif; }'
    )

    # German content
    de_dir = root / 'de'
    de_dir.mkdir(exist_ok=True)
    (de_dir / 'index.html').write_text(
        '<html><head><title>DE</title></head>'
        '<body><h1>Deutsche Seite</h1></body></html>'
    )
    (de_dir / 'style.css').write_text(
        'body { font-family: sans-serif; }'
    )

    # Shared assets — use .txt instead of .gitkeep to avoid extension issues
    assets_dir = root / 'shared-assets' / 'images'
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / 'placeholder.txt').write_text('placeholder')

    return root


def create_test_users() -> tuple[CustomUser, CustomUser]:
    """Create a Creator and an Approver user for testing."""
    creator = CustomUser.objects.create_user(
        username='test_creator',
        password='testpass123!',
        email='creator@test.com',
        role=CustomUser.ROLE_CREATOR,
    )
    approver = CustomUser.objects.create_user(
        username='test_approver',
        password='testpass123!',
        email='approver@test.com',
        role=CustomUser.ROLE_APPROVER,
    )
    return creator, approver


def login_as_user(client: Client, user: CustomUser) -> None:
    """Log the test client in as the specified user."""
    client.login(username=user.username, password='testpass123!')