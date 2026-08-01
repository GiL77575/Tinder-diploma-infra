#!/usr/bin/env python3
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def main():
    base_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(base_dir / 'src'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Install dependencies from requirements.txt."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
