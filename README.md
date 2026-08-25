# Система автоматизации производственного процесса обслуживания и учета газовых баллонов

## Установка и запуск проекта

Зависимости проекта управляются через **[uv](https://docs.astral.sh/uv/)** (`pyproject.toml` + `uv.lock`). Требуется **Python 3.12**.

Здесь и далее команды приведены для Windows; отличия для Linux/Mac указаны отдельно.

1. Клонируем репозиторий:
   ```bash
   git clone https://github.com/AvectisDev/PinskGNS.git
   cd PinskGNS
   ```
2. Устанавливаем uv (если ещё не установлен):
   ```bash
   # Windows (PowerShell)
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

   # Linux/Mac
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
3. Создаём виртуальное окружение и устанавливаем зависимости из lock-файла:
   ```bash
   uv sync
   ```
   Для разработки (включая `django-debug-toolbar`):
   ```bash
   uv sync --group dev
   ```
4. Активируем окружение:
   ```bash
   # Windows
   .venv\Scripts\activate

   # Linux/Mac
   source .venv/bin/activate
   ```
   Альтернатива без активации: выполнять команды через `uv run` из корня репозитория (например `uv run --directory GNS python manage.py migrate`).
5. Создаём файл `GNS/.env` с переменными окружения (`SECRET_KEY`, `DEBUG`, параметры БД и т.д.).
6. Переходим в каталог Django-проекта и применяем миграции:
   ```bash
   cd GNS
   python manage.py migrate
   ```
7. Собираем статические файлы (нужно для раздачи статики через Daphne):
   ```bash
   python manage.py collectstatic --noinput
   ```
8. Запускаем локальный сервер через **Daphne** (ASGI сервер):
   ```bash
   daphne GNS.asgi:application --bind 0.0.0.0 -p 8000 --application-close-timeout 10
   ```
9. По адресу `http://localhost:8000` будет доступна главная страница с архивом баллонов.
10. По адресу `http://localhost:8000/api/swagger` будет доступно описание API для проекта.

### Обновление зависимостей

После изменений в `pyproject.toml` или получения обновлённого `uv.lock`:

```bash
uv sync
# или с dev-зависимостями:
uv sync --group dev
```

## OpenAPI

Спецификация API генерируется из Django-кода (`drf-spectacular`) и хранится в репозитории:

- `docs/openapi/pinskgns.yaml` — полная OpenAPI 3.0 схема

После изменений в API перегенерируйте файл из каталога `GNS`:

```bash
python manage.py spectacular --file ../docs/openapi/pinskgns.yaml
```

Тот же JSON/YAML доступен на работающем сервере:

- `http://localhost:8000/api/schema/` — схема
- `http://localhost:8000/api/swagger/` — Swagger UI
- `http://localhost:8000/api/redoc/` — ReDoc

## Redis

Redis используется в проекте для следующих целей:

- **База данных 0**: 
  - Брокер сообщений для Celery (`CELERY_BROKER_URL`)
  - Хранилище результатов выполнения задач Celery (`CELERY_RESULT_BACKEND`)
  
- **База данных 1**: 
  - Django кэш для приложения (`CACHES`)
  - Хранение стека баллонов для карусели наполнения (`reader_8_balloon_stack`)
  - Кэширование запросов от постов наполнения для предотвращения дублирования обработки
  - Хранение статистики и других временных данных

Для запуска Redis используйте:
```bash
redis-server
```

## Celery

Проект использует Celery для асинхронной обработки задач. Для работы Celery необходимо запустить:

1. **Celery Worker** (обработчик задач):
   ```bash
   celery -A GNS worker --loglevel=info --concurrency=8
   ```

2. **Celery Beat** (планировщик периодических задач):
   ```bash
   celery -A GNS beat --loglevel=info
   ```

### Периодические задачи (Celery Beat)

В проекте настроены следующие периодические задачи:

- **railway_tank_processing** (`railway_service.tasks.railway_tank_processing`)
  - Обработка данных по железнодорожным цистернам
  - Выполняется каждые 10 секунд

- **railway_batch_processing** (`railway_service.tasks.railway_batch_processing`)
  - Обработка партий железнодорожных цистерн
  - Выполняется каждые 20 минут

- **auto_gas_processing** (`autogas.tasks.auto_gas_processing`)
  - Обработка данных по автоцистернам
  - Выполняется каждые 10 секунд

- **kpp_processing** (`transport.tasks.kpp_processing`)
  - Обработка данных от контрольно-пропускного пункта (КПП)
  - Выполняется каждую минуту

- **kpp_close_transport** (`transport.tasks.kpp_close_transport`)
  - Закрытие транспорта на КПП в конце рабочего дня
  - Выполняется ежедневно в 18:00

### Задачи по требованию

- **generate_1c_file** (`ttn.tasks.generate_1c_file`)
  - Генерация файла для 1С по номеру ТТН
  - Вызывается по требованию через API

## Management команды

### RFID метки

Команда для работы с RFID-считывателями баллонов запускается автоматически при старте приложения через ASGI (см. `GNS/asgi.py`). Доступны две версии команды:

#### Версия с Celery (рекомендуется)
```bash
python -m filling_station.management.commands.rfid_utils.feig_protocol
```

#### Версия с прямым вызовом сервисов (альтернативная)
```bash
python -m filling_station.management.commands.rfid_utils.feig_protocol_direct
```

**Назначение:**
- Подключение к RFID-считывателям по протоколу Feig
- Чтение NFC-меток с баллонов
- Отслеживание состояния входов считывателей (оптические датчики)
- Обработка данных баллонов через сервисы Django
- Управление светодиодными индикаторами на считывателях (зеленый - баллон полный, мигание - баллон пустой)

**Архитектура обработки данных:**

**Celery версия:**
- RFID процесс отправляет данные в очередь Celery
- Celery worker обрабатывает задачи асинхронно
- Подходит для высокой нагрузки и масштабируемости

**Прямая версия:**
- RFID процесс напрямую вызывает функции сервисов
- Синхронная обработка без очередей
- Более простая архитектура, подходит для меньшей нагрузки

**Особенности:**
- Асинхронная обработка нескольких считывателей одновременно
- Загрузка конфигурации считывателей из базы данных (таблица `ReaderSettings`)
- Автоматическая обработка буфера меток и очистка после чтения
- Интеграция с системой Мириада для отправки статусов

### Карусель наполнения

Команда для работы с каруселью наполнения баллонов запускается автоматически при старте приложения через ASGI, но также может быть запущена вручную через management команду:

```bash
python manage.py carousel_process
```

Или напрямую:

```bash
python -m carousel.management.commands.carousel.main
```

**Назначение:**
- Обмен данными с постами наполнения баллонов через последовательный порт (COM порт)
- Получение данных о весе баллонов с постов наполнения
- Получение данных о баллонах из нативной Redis-очереди (сформированной RFID-считывателем)
- Сохранение данных о наполнении напрямую через сервисы и ORM Django
- Обработка команд управления каруселью (поворот, остановка)

**Особенности:**
- Работа через последовательный порт (по умолчанию COM3, скорость 9600 бод)
- Атомарная FIFO-очередь Redis `reader_<N>_balloon_queue` (`LPUSH`/`RPOP`)
- Общая бизнес-логика для COM-процесса и совместимого API
- Дедупликация повторных запросов в памяти COM-процесса
- Автоматический перезапуск при ошибках с задержкой 5 минут

**Конфигурация:**
- Настройки карусели хранятся в базе данных в таблице `CarouselSettings`
- Настройки читаются через Django ORM без отдельного подключения к PostgreSQL
- `CAROUSEL_NUMBER` — номер запускаемой карусели (по умолчанию `1`)
- `CAROUSEL_<N>_COM_PORT` — COM-порт карусели (для первой — `CAROUSEL_1_COM_PORT`, по умолчанию `COM3`)
- `CAROUSEL_<N>_BAUD_RATE` — скорость порта (по умолчанию `9600`)
- `CAROUSEL_<N>_RFID_READER` — номер RFID-считывателя, формирующего очередь (по умолчанию `8`)
