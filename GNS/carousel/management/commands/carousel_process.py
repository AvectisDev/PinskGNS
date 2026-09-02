import os
import subprocess
import sys
from pathlib import Path

from django.core.management.base import BaseCommand


DJANGO_PROJECT_DIR = Path(__file__).resolve().parents[3]


class Command(BaseCommand):
    help = (
        'Запускает subprocess listener постов наполнения '
        '(carousel.management.commands.carousel.main)'
    )

    def handle(self, *args, **kwargs):
        """Создаёт отдельный процесс listener с текущими переменными окружения."""
        env = os.environ.copy()
        subprocess.Popen(
            [
                sys.executable,
                '-m',
                'carousel.management.commands.carousel.main',
            ],
            env=env,
            cwd=DJANGO_PROJECT_DIR,
        )
