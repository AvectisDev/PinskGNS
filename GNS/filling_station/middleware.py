"""Middleware для измерения длительности обработки HTTP-запросов."""

import time
import logging

logger = logging.getLogger(__name__)

class TimingMiddleware:
    """Логирует время обработки каждого запроса без изменения ответа."""

    def __init__(self, get_response):
        """
        Сохраняет следующий обработчик цепочки middleware.

        Args:
            get_response: Callable следующего middleware или view.
        """
        self.get_response = get_response

    def __call__(self, request):
        """
        Замеряет длительность обработки запроса и пишет её в лог.

        Запускается на каждый HTTP-запрос. Побочный эффект — запись
        в логгер ``filling_station.middleware``; тело ответа не меняется.

        Args:
            request: Объект HTTP-запроса Django.

        Returns:
            HttpResponse: Ответ, полученный от следующего обработчика.
        """
        # Запись времени начала обработки запроса
        start_time = time.time()

        # Обработка запроса
        response = self.get_response(request)

        # Запись времени окончания обработки запроса
        end_time = time.time()
        duration = end_time - start_time

        logger.info(f"Request to {request.path} took {duration:.4f} seconds")

        return response
