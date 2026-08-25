# Deploy: Windows Server (NSSM + uv + nginx in Docker)

Схема: Daphne, Celery, Postgres и Redis работают на хосте; nginx в Docker Desktop раздаёт `/static/` и `/media/` и проксирует остальное на Daphne `127.0.0.1:8000`.

Пути ниже предполагают установку в `D:\Program Files\PinskGNS` (корень репозитория, рядом `.venv` после `uv sync`).

## NSSM: переход на `.venv` (uv)

В **Startup directory** указывайте путь **без** `cd`.

Path для всех трёх служб:

`D:\Program Files\PinskGNS\.venv\Scripts\python.exe`

Startup directory для всех трёх служб:

`D:\Program Files\PinskGNS\GNS`

### django (Daphne)

| Поле | Значение |
|------|----------|
| Path | `D:\Program Files\PinskGNS\.venv\Scripts\python.exe` |
| Startup directory | `D:\Program Files\PinskGNS\GNS` |
| Arguments | `-m daphne GNS.asgi:application --bind 127.0.0.1 -p 8000 --application-close-timeout 10` |

### celery

| Поле | Значение |
|------|----------|
| Path | `D:\Program Files\PinskGNS\.venv\Scripts\python.exe` |
| Startup directory | `D:\Program Files\PinskGNS\GNS` |
| Arguments | `-m celery -A GNS worker --pool=threads --concurrency=8 --loglevel=info` |

### celery beat

| Поле | Значение |
|------|----------|
| Path | `D:\Program Files\PinskGNS\.venv\Scripts\python.exe` |
| Startup directory | `D:\Program Files\PinskGNS\GNS` |
| Arguments | `-m celery -A GNS beat --loglevel=info` |

Рекомендуется I/O redirection в каталог логов, например:

- `D:\Program Files\PinskGNS\logs\daphne.out.log` / `daphne.err.log`
- `D:\Program Files\PinskGNS\logs\celery.out.log` / `celery.err.log`
- `D:\Program Files\PinskGNS\logs\celery-beat.out.log` / `celery-beat.err.log`

После смены Path: Stop → Apply → Start. Учётка службы должна иметь доступ к каталогу проекта и `.venv`.

### Обновление зависимостей на сервере

```powershell
cd "D:\Program Files\PinskGNS"
uv sync
# затем Restart служб django / celery / celery beat
```

Глобальный Python312 + pip для этих служб больше не используются.

## Чеклист на сервере

1. Убедиться, что выполнен `uv sync` и есть `.venv`.
2. Собрать статику:
   ```powershell
   cd "D:\Program Files\PinskGNS"
   .\.venv\Scripts\python.exe GNS\manage.py collectstatic --noinput
   ```
3. Обновить параметры NSSM (таблицы выше), Daphne слушает `127.0.0.1:8000`.
4. Перезапустить службы django / celery / celery beat.
5. Запустить nginx:
   ```powershell
   cd "D:\Program Files\PinskGNS\deploy"
   docker compose -f docker-compose.nginx.yml up -d
   ```
6. В брандмауэре открыть TCP 80; прямой доступ к `:8000` снаружи закрыть после проверки.
7. Настроить имя `gns-gas` (см. ниже) и проверить:
   - `http://gns-gas/` — главная
   - `http://gns-gas/static/...` — статика с nginx
   - `http://gns-gas/api/swagger` — API docs

При смене пути установки поправьте volume-пути в [docker-compose.nginx.yml](docker-compose.nginx.yml).

## Имя сайта `http://gns-gas`

Без порта (`:80`) работает только через nginx. Daphne остаётся на `127.0.0.1:8000`.

1. В `C:\Windows\System32\drivers\etc\hosts` (блокнот от администратора) добавьте строку:
   - на **самом сервере** (браузер на сервере):
     ```
     127.0.0.1   gns-gas
     ```
   - на **клиентских ПК** в сети — IP сервера, например:
     ```
     10.10.12.253   gns-gas
     ```
2. В nginx уже задано `server_name gns-gas` ([nginx/nginx.conf](nginx/nginx.conf)). После правки конфига:
   ```powershell
   cd "D:\Program Files\PinskGNS\deploy"
   docker compose -f docker-compose.nginx.yml up -d --force-recreate
   ```
3. В Django уже добавлены `gns-gas` в `ALLOWED_HOSTS` и `http://gns-gas` в `CSRF_TRUSTED_ORIGINS`. Перезапустите службу django.

Открывайте: `http://gns-gas` (не `:8000`).

## DEBUG и хосты

Пока `DEBUG=TRUE`, Django может отдавать static/media сам, но внешний вход должен идти на nginx `:80`. Для production позже: `DEBUG=False` и актуальные `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS`.
