import psycopg2
from datetime import datetime

DB_CRD = {'name': 'PinskGNS', 'host': 'localhost', 'user': 'postgres', 'password': '.avectis1', 'port': '5432'}


def write_balloons_amount(reader_number: int):
    """Функция записывает в базу данных количество баллонов, пройденных через каждый считыватель"""
    try:
        conn = psycopg2.connect(dbname=DB_CRD['name'],
                                host=DB_CRD['host'],
                                user=DB_CRD['user'],
                                password=DB_CRD['password'],
                                port=DB_CRD['port'])
        conn.autocommit = True
        current_date = datetime.now()
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT * "
                           f"FROM public.filling_station_balloonamount "
                           f"WHERE reader_id = '{reader_number}' AND change_date = '{current_date.date()}'")
            select_data = cursor.fetchall()
            if len(select_data) == 0:  # если данных ещё нет в базе
                cursor.execute(
                    f"INSERT INTO filling_station_balloonamount (reader_id, amount_of_balloons, change_date, change_time) "
                    f"VALUES ('{reader_number}', '{1}', '{current_date.date()}', '{current_date.time()}')")
                print("Amount added to database")
            else:
                cursor.execute(f"UPDATE public.filling_station_balloonamount "
                               f"SET amount_of_balloons = amount_of_balloons + 1, change_time = '{current_date.time()}' "
                               f"WHERE reader_id = '{reader_number}' AND change_date = '{current_date.date()}'")
                print("Data updated")
    except:
        print('Can`t establish connection to database')
