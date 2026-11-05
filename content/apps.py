from django.apps import AppConfig


class ContentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'content'
    verbose_name = 'Content Management'

    def ready(self):
        """Ensure required storage directories exist at startup."""
        from django.conf import settings

        directories_to_create = [
            settings.STORAGE_ROOT,
            settings.WORKING_DIR,
            settings.WORKING_DIR / 'test',
            settings.WORKING_DIR / 'production',
            settings.ARCHIVE_DIR,
        ]

        for directory in directories_to_create:
            directory.mkdir(parents=True, exist_ok=True)