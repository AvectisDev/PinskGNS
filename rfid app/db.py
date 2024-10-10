import os
import asyncpg
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


async def write_balloons_amount(reader: dict, from_who: str):
    """Функция записывает в базу данных количество баллонов, пройденных через каждый считыватель"""
    try:
        conn = await asyncpg.connect(
            database=os.environ.get('DB_NAME'),
            host=os.environ.get('DB_HOST'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD'),
            port='5432'
        )

        current_date = datetime.now()
        select_query = """SELECT * 
                          FROM public.filling_station_balloonamount 
                          WHERE reader_id = $1 AND change_date = $2"""

        select_data = await conn.fetch(select_query, reader['number'], current_date.date())

        if len(select_data) == 0:  # если данных еще нет в базе
            if from_who == 'sensor':
                insert_query = """INSERT INTO filling_station_balloonamount 
                                  (reader_id, amount_of_balloons, change_date, change_time, amount_of_rfid, reader_status) 
                                  VALUES ($1, $2, $3, $4, $5, $6)"""
                await conn.execute(insert_query, reader['number'], 1, current_date.date(), current_date.time(), 0,
                                   reader['status'])
            if from_who == 'rfid':
                insert_query = """INSERT INTO filling_station_balloonamount 
                                  (reader_id, amount_of_balloons, change_date, change_time, amount_of_rfid, reader_status) 
                                  VALUES ($1, $2, $3, $4, $5, $6)"""
                await conn.execute(insert_query, reader['number'], 0, current_date.date(), current_date.time(), 1,
                                   reader['status'])

            print("Amount added to database")
        else:
            if from_who == 'sensor':
                update_query = """UPDATE public.filling_station_balloonamount 
                                  SET amount_of_balloons = amount_of_balloons + 1, change_time = $1 
                                  WHERE reader_id = $2 AND change_date = $3"""
                await conn.execute(update_query, current_date.time(), reader['number'], current_date.date())
            if from_who == 'rfid':
                update_query = """UPDATE public.filling_station_balloonamount
                                  SET amount_of_rfid = amount_of_rfid + 1, change_time = $1 
                                  WHERE reader_id = $2 AND change_date = $3"""
                await conn.execute(update_query, current_date.time(), reader['number'], current_date.date())

            print("Data updated")

    except Exception as error:
        print('Can`t establish connection to database:', error)

    finally:
        await conn.close()
