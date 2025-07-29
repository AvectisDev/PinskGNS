from django.core.management.base import BaseCommand
import subprocess


class Command(BaseCommand):
    help = 'Запуск main.py - приложения обработки данных с постов наполнения УНБ'

    def handle(self, *args, **kwargs):
        subprocess.Popen([
            'python', '-m', 'carousel.management.commands.carousel.main'
        ])
