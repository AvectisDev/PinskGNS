"""
Listener постов наполнения карусели.

Долгоживущий asyncio-процесс: подключается к NPort W2150A (TCP Server)
для каждой карусели с заданным ``CAROUSEL_<N>_TCP_HOST``, читает 8-байтные
кадры от контроллеров постов УНБ, обогащает их паспортом баллона из Redis
и сохраняет результат в Django ORM.

Поток данных::

    Пост УНБ → RS-485 → NPort → TCP → async listener
        → Redis (паспорт RFID) + CarouselSettings (БД)
        → ответ посту + запись Carousel

Модули пакета:
    config      — переменные окружения и таймауты
    transport   — async TCP-клиент к NPort
    protocol    — разбор кадров и CRC
    cache       — дедупликация повторных запросов
    processing  — бизнес-логика запросов 0x7A / 0x70
    runner      — asyncio-цикл и переподключение по каруселям
"""
