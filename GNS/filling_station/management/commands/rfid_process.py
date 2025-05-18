from django.core.management.base import BaseCommand
import subprocess


class Command(BaseCommand):
    help = 'Запуск main.py - приложения обработки RFID считывателей'

    def handle(self, *args, **kwargs):
        subprocess.Popen([
            'python', '-m', 'filling_station.management.commands.rfid.main'
        ])
