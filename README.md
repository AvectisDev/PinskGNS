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

В `settings.py` Redis разделён по базам:

- **База данных 0** (`CELERY_BROKER_URL = redis://localhost:6379/0`):
  - брокер сообщений Celery
  - результаты задач не сохраняются (`CELERY_TASK_IGNORE_RESULT = True`, `CELERY_RESULT_BACKEND` не используется)

- **База данных 1** (`CACHES` → `redis://localhost:6379/1`):
  - Django cache приложения (статистика, временные значения OPC, антидубли на КПП и т.п.)
  - FIFO-очереди баллонов для карусели: `reader_<N>_balloon_queue` (`LPUSH` / `RPOP` через `core.redis_queue`, тот же Redis DB)
  - счётчики метрик карусели: `carousel_<N>_metric_<name>`

Дедупликация повторных запросов с постов наполнения хранится **в памяти** процесса карусели (`recent_requests`), не в Redis.

Для запуска Redis:
```bash
redis-server
```

## Celery

Проект использует Celery для асинхронной и периодической обработки. Из каталога `GNS` с активированным окружением нужно запустить:

1. **Celery Worker** (обработчик задач):
   ```bash
   celery -A GNS worker --loglevel=info --concurrency=8
   ```

2. **Celery Beat** (планировщик периодических задач):
   ```bash
   celery -A GNS beat --loglevel=info
   ```

Расписание задаётся в `GNS/GNS/settings.py` (`CELERY_BEAT_SCHEDULE`). Брокер — Redis DB 0; результаты задач не сохраняются (`CELERY_TASK_IGNORE_RESULT = True`).

### Периодические задачи (Celery Beat)

- **railway_tank_processing** (`railway_service.tasks.railway_tank_processing`)
  - обработка данных по железнодорожным цистернам (management-команда `railway_tank`)
  - каждые 10 секунд (`expires=9`)

- **railway_batch_processing** (`railway_service.tasks.railway_batch_processing`)
  - проверка/обработка активных ж/д партий (`railway_batch`)
  - каждые 20 минут (`crontab(minute='*/20')`)

- **auto_gas_processing** (`autogas.tasks.auto_gas_processing`)
  - обработка данных по автоцистернам (`auto_gas_batch`)
  - каждые 10 секунд (`expires=9`)

- **kpp_processing** (`transport.tasks.kpp_processing`)
  - обработка данных КПП (`kpp_processing`)
  - каждую минуту (`expires=55`)

- **kpp_close_transport** (`transport.tasks.kpp_close_transport`)
  - закрытие транспорта на КПП в конце рабочего дня (`kpp_close_transport`)
  - ежедневно в 18:00 (`crontab(hour=18, minute=0)`)

- **fetch_current_ttn_from_miriada** (`ttn.tasks.fetch_current_ttn_from_miriada`)
  - синхронизация текущих ТТН из Мириады в БД (`sync_current_ttn_from_miriada`)
  - ежедневно в 22:00 (`crontab(hour=22, minute=0)`)

### Задачи по требованию

- **generate_1c_file** (`ttn.tasks.generate_1c_file`)
  - генерация файла для 1С по номеру ТТН
  - ставится в очередь через `ttn.services.enqueue_1c_file` (`transaction.on_commit` → `.delay`), например при обработке/закрытии ТТН

## Management команды

### RFID метки

Процесс RFID запускается автоматически при старте приложения через ASGI (`GNS/GNS/asgi.py`) как отдельный subprocess:

```bash
python -m filling_station.management.commands.rfid_utils.feig_protocol
```

Работает в **Notification Mode**: считыватели сами присылают события на TCP-слушатель процесса (по умолчанию `0.0.0.0:8002`, задаётся `RFID_NOTIFICATION_LISTEN_HOST` / `RFID_NOTIFICATION_LISTEN_PORT`). Обработка данных — **прямые синхронные вызовы** Django-сервисов через `sync_to_async` (без Celery).

**Назначение:**
- Приём событий от RFID-считывателей по протоколу Feig (метка `0x2B`, вход/оптика `0x2C`)
- Чтение NFC-меток и обработка баллонов через `processing_request_with_nfc` / `processing_request_without_nfc`
- Индикация результата на считывателе: зелёный свет — успех, мигание — ошибка
- При `ReaderSettings.need_cache=True` — добавление баллона в Redis-очередь `reader_<N>_balloon_queue` (для карусели)
- Выборочная отправка статуса в Мириаду сразу после чтения (для считывателя наполнения; остальные — при закрытии партии)

**Особенности:**
- Один asyncio-сервер обслуживает несколько считывателей параллельно
- Конфигурация загружается из БД (`ReaderSettings`: `number`, `ip`, `port`, `status`, `function`, `need_cache`) один раз при старте процесса
- Отдельное исходящее TCP-соединение к каждому считывателю для команд (LED и т.п.)

### Карусель наполнения

Процесс карусели запускается автоматически при старте приложения через ASGI (`GNS/GNS/asgi.py`) как отдельный subprocess. Также может быть запущен вручную:

```bash
python manage.py carousel_process
```

Или напрямую:

```bash
python -m carousel.management.commands.carousel.main
```

Для нескольких каруселей запускается отдельный процесс на каждую с своим `CAROUSEL_NUMBER` и переменными `CAROUSEL_<N>_*` в `.env`.

**Назначение:**
- Обмен данными с постами наполнения через последовательный порт (COM)
- Обработка запросов поста: пустой баллон / запрос наполнения (`0x7a`) и фиксация полного веса (`0x70`)
- Получение паспорта баллона из Redis-очереди RFID-считывателя
- Валидация весов по настройкам из БД и ответ посту с целевым полным весом (если не `read_only`)
- Сохранение состояния постов через ORM (`Carousel`)

**Особенности:**
- Чтение 8-байтных кадров с COM-порта, проверка CRC-16
- Атомарная FIFO-очередь Redis `reader_<N>_balloon_queue` (`LPUSH` / `RPOP`)
- Дедупликация повторных запросов в памяти процесса (~2 с)
- Автоматический перезапуск при ошибках с задержкой 5 минут

**Конфигурация экземпляра (`.env` / переменные окружения)** — читаются в `carousel/management/commands/carousel/main.py`, в БД не хранятся:

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `CAROUSEL_NUMBER` | номер запускаемой карусели (`N`) | `1` |
| `CAROUSEL_<N>_COM_PORT` | COM-порт (для карусели 1 — `CAROUSEL_1_COM_PORT`) | `COM3` |
| `CAROUSEL_<N>_BAUD_RATE` | скорость порта | `9600` |
| `CAROUSEL_<N>_RFID_READER` | номер RFID-считывателя, чья очередь используется | `8` |

**Настройки из БД (`CarouselSettings`)** — режим работы и весовая политика:

- `read_only` — только чтение с постов без ответа целевым весом
- `use_weight_management` / `use_common_correction` / `weight_correction_value`
- диапазоны весов: `min_balloon_weight_*`, `max_balloon_weight_*`, `passport_weight_diff_*`
- корректоры постов: `post_1_correction` … `post_20_correction`
