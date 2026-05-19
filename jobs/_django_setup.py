"""Bootstrap Django ORM for standalone job execution (no web server needed)."""
import os
import sys
from pathlib import Path


def setup(settings_module: str = 'config.settings') -> None:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)
    import django
    django.setup()
