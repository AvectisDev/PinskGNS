"""
Кастомные исключения для приложения filling_station.
"""


class FillingStationException(Exception):
    """Базовое исключение для приложения filling_station."""
    pass


class ReaderNotFoundError(FillingStationException):
    """Исключение, возникающее когда считыватель не найден."""
    pass


class BalloonNotFoundError(FillingStationException):
    """Исключение, возникающее когда баллон не найден."""
    pass


class MiriadaAPIError(FillingStationException):
    """Исключение, возникающее при ошибках взаимодействия с API Мириады."""
    pass


class BatchNotFoundError(FillingStationException):
    """Исключение, возникающее когда партия баллонов не найдена."""
    pass


class TransportNotFoundError(FillingStationException):
    """Исключение, возникающее когда транспорт не найден."""
    pass

