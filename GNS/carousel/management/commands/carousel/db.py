import os
import asyncpg
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from typing import Optional

load_dotenv()


def fetch_carousel_settings() -> Optional[dict]:
    """Функция получает все данные из таблицы CarouselSettings и возвращает их в виде словаря"""
    conn = None
    try:
        # Подключение к базе данных
        conn = psycopg2.connect(
            dbname=os.environ.get('DB_NAME'),
            host=os.environ.get('DB_HOST'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD'),
            port=os.environ.get('DB_PORT')
        )

        # Создаем курсор для работы с базой данных
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Выполняем запрос для получения всех данных из таблицы CarouselSettings
            query = "SELECT * FROM public.carousel_carouselsettings"
            cursor.execute(query)
            records = cursor.fetchall()

            # Преобразуем записи в список словарей
            carousel_settings = []
            for record in records:
                carousel_settings.append(dict(record))

            if carousel_settings:
                return carousel_settings[0]
            return None

    except Exception as error:
        print('Can`t establish connection to database:', error)
        return None

    finally:
        if conn:
            conn.close()
