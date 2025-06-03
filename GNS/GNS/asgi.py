import os
import sys
import signal
import subprocess

# Глобальный список процессов
processes = []

def start_processes():
    """Запускаем дочерние процессы и сохраняем их объекты."""
    global processes
    print('Starting processes...')
    p1 = subprocess.Popen(['python', '-m', 'filling_station.management.commands.rfid.main'])
    p2 = subprocess.Popen(['python', '-m', 'carousel.management.commands.carousel.main'])
    processes.extend([p1, p2])
    print(f'Processes is started: {processes}')

def stop_processes():
    """Завершаем дочерние процессы."""
    print('Stoping processes...')
    for p in processes:
        try:
            p.terminate()
        except Exception as e:
            print(f'Error while stopping processes: {e}')
    # Ждем завершения или принудительно убиваем
    for p in processes:
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            print('The process did not complete within the allotted time. kill')
            p.kill()

def handle_exit(signum, frame):
    """Обработчик сигнала для корректной остановки."""
    stop_processes()
    sys.exit(0)

# Устанавливаем обработчики сигналов для graceful shutdown
signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

# Запускаем процессы при инициализации ASGI
start_processes()

# Стандартная настройка Django ASGI
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GNS.settings')
from django.core.asgi import get_asgi_application

application = get_asgi_application()