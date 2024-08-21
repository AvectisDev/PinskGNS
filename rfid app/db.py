import psycopg2
from datetime import datetime

DB_CRD = {'name': 'PinskGNS', 'host': 'localhost', 'user': 'postgres', 'password': '.avectis1', 'port': '5432'}


def write_balloon_passport(passport: dict):
    """Функция записывает в базу данных номер метки, статус, дату и время проведения операции считывания"""
    current_date = datetime.now()
    try:
        conn = psycopg2.connect(dbname=DB_CRD['name'],
                                host=DB_CRD['host'],
                                user=DB_CRD['user'],
                                password=DB_CRD['password'],
                                port=DB_CRD['port'])
        conn.autocommit = True
        with conn.cursor() as cursor:
            cursor.execute(f"INSERT INTO filling_station_balloon (nfc_tag, serial_number, creation_date, size, netto, "
                           f"brutto, current_examination_date, next_examination_date, manufacturer, wall_thickness, "
                           f"status, filling_status, update_passport_required, change_date, change_time, user_id)"
                           f"VALUES ('{passport['nfc_tag']}', '{passport['serial_number']}', "
                           f"Null, '{passport["size"]}', '{passport["netto"]}', "
                           f"'{passport["brutto"]}', Null, "
                           f"Null, '{passport["manufacturer"]}', "
                           f"'{passport["wall_thickness"]}', '{passport["status"]}', '{passport["filling_status"]}', "
                           f"'{passport["update_passport_required"]}', "
                           f"'{current_date.date()}', '{current_date.time()}', '{1}')")
            print("Data added")
        conn.close()
    except:
        print('Can`t establish connection to database')


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


def check_passport(nfc_tag: str):
    """Функция проверяет наличие и заполненность паспорта в базе данных"""
    try:
        conn = psycopg2.connect(dbname=DB_CRD['name'],
                                host=DB_CRD['host'],
                                user=DB_CRD['user'],
                                password=DB_CRD['password'],
                                port=DB_CRD['port'])
        conn.autocommit = True
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT * "
                           f"FROM public.filling_station_balloon "
                           f"WHERE nfc_tag = '{nfc_tag}' ORDER BY id DESC LIMIT 1")
            balloon_id = cursor.fetchall()
            if balloon_id:
                if balloon_id[0][2] is None or balloon_id[0][5] is None or balloon_id[0][6] is None:
                    return False, {"status": "no data"}
                else:
                    passport = {
                        'nfc_tag': balloon_id[0][1],
                        'serial_number': balloon_id[0][2],
                        'creation_date': balloon_id[0][3],
                        'size': balloon_id[0][4],
                        'netto': balloon_id[0][5],
                        'brutto': balloon_id[0][6],
                        'current_examination_date': balloon_id[0][7],
                        'next_examination_date': balloon_id[0][8],
                        'manufacturer': balloon_id[0][10],
                        'wall_thickness': balloon_id[0][11],
                        'status': balloon_id[0][9],
                        'filling_status': balloon_id[0][15],
                        'update_passport_required': balloon_id[0][16],
                        'change_date': balloon_id[0][12],
                        'change_time': balloon_id[0][13],
                        'user': balloon_id[0][14]
                    }
                    return True, passport
            else:
                return False, {"status": "no passport"}
    except:
        print('Can`t establish connection to database')
