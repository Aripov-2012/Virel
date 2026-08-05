from django.apps import AppConfig


class BlogConfig(AppConfig):
    name = 'blog'

    def ready(self):
        # Ensure social login signals are registered
        from . import signals  # noqa: F401
