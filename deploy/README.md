# Deploy: Windows Server (NSSM + uv + nginx in Docker)

Схема: Daphne, Celery, Postgres и Redis на хосте (NSSM + `.venv`); nginx в Docker Desktop раздаёт `/static/` и `/media/` и проксирует остальное на Daphne `127.0.0.1:8000`.

Установка: `D:\Program Files\PinskGNS` (корень репозитория, рядом `.venv`).

Службы django / celery / celery beat уже переведены на `.venv` — параметры NSSM см. [ниже](#справочник-nssm).

## Текущий шаг: nginx на :8080

Порт хоста **8080** (внутри контейнера — 80), чтобы не трогать системный `:80` Windows.

1. Собрать статику (если ещё не собрана после обновления кода):
   ```powershell
   cd "D:\Program Files\PinskGNS"
   .\.venv\Scripts\python.exe GNS\manage.py collectstatic --noinput
   ```
2. Запустить / пересоздать nginx:
   ```powershell
   cd "D:\Program Files\PinskGNS\deploy"
   docker compose -f docker-compose.nginx.yml up -d --force-recreate
   ```
3. В брандмауэре открыть TCP **8080**; прямой доступ к `:8000` снаружи закрыть после проверки.
4. После правок `settings.py` — Restart службы django.
5. Имя `gns-gas` в `hosts` (см. ниже) и проверка:
   - `http://gns-gas:8080/` — главная
   - `http://gns-gas:8080/static/...` — статика с nginx
   - `http://gns-gas:8080/api/swagger` — API docs

При смене пути установки поправьте volume-пути в [docker-compose.nginx.yml](docker-compose.nginx.yml).

### Имя сайта `http://gns-gas:8080`

1. В `C:\Windows\System32\drivers\etc\hosts` (блокнот от администратора):
   - на **сервере**: `127.0.0.1   gns-gas`
   - на **клиентах**: `10.10.12.253   gns-gas` (IP сервера)
2. В nginx: `server_name gns-gas` ([nginx/nginx.conf](nginx/nginx.conf)).
3. В Django: `gns-gas` в `ALLOWED_HOSTS`, `http://gns-gas:8080` в `CSRF_TRUSTED_ORIGINS`.

Открывайте: `http://gns-gas:8080` (не `:8000`).

### Обновление зависимостей

```powershell
cd "D:\Program Files\PinskGNS"
uv sync
# затем Restart служб django / celery / celery beat
```

## DEBUG и хосты

Пока `DEBUG=TRUE`, Django может отдавать static/media сам, но внешний вход должен идти на nginx `:8080`. Для production позже: `DEBUG=False` и актуальные `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS`.

## Справочник: NSSM

Path для всех трёх служб: `D:\Program Files\PinskGNS\.venv\Scripts\python.exe`  
Startup directory: `D:\Program Files\PinskGNS\GNS` (без `cd`).

### django (Daphne)

| Поле | Значение |
|------|----------|
| Arguments | `-m daphne GNS.asgi:application --bind 127.0.0.1 -p 8000 --application-close-timeout 10` |

### celery

| Поле | Значение |
|------|----------|
| Arguments | `-m celery -A GNS worker --pool=threads --concurrency=8 --loglevel=info` |

### celery beat

| Поле | Значение |
|------|----------|
| Arguments | `-m celery -A GNS beat --loglevel=info` |

Логи (I/O redirection), например:

- `D:\Program Files\PinskGNS\logs\daphne.out.log` / `daphne.err.log`
- `D:\Program Files\PinskGNS\logs\celery.out.log` / `celery.err.log`
- `D:\Program Files\PinskGNS\logs\celery-beat.out.log` / `celery-beat.err.log`
