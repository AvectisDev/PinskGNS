from django.test import TestCase
from django.utils import timezone
from django.db import IntegrityError

from filling_station.models import DailyReaderCounter, ReaderSettings


class DailyReaderCounterTests(TestCase):
    def setUp(self):
        self.reader = ReaderSettings.objects.create(
            number=5,
            ip='10.10.2.24',
            port=10001,
            status='active',
            function='full',
            need_cache=True,
        )
        self.today = timezone.now().date()

    def test_get_or_create_once_per_reader_day(self):
        # первая попытка
        obj, created = DailyReaderCounter.objects.get_or_create(
            number=self.reader,
            day=self.today,
            defaults={'amount_of_rfid': 0, 'amount_of_sensor': 0}
        )
        self.assertTrue(created)
        # вторая попытка — не создаёт новую
        obj2, created2 = DailyReaderCounter.objects.get_or_create(
            number=self.reader,
            day=self.today,
            defaults={'amount_of_rfid': 0, 'amount_of_sensor': 0}
        )
        self.assertFalse(created2)
        self.assertEqual(obj.pk, obj2.pk)

    def test_add_rfid_increments_atomically(self):
        DailyReaderCounter.add_rfid(self.reader)
        row = DailyReaderCounter.objects.get(number=self.reader, day=self.today)
        self.assertEqual(row.amount_of_rfid, 1)

        DailyReaderCounter.add_rfid(self.reader)
        row.refresh_from_db()
        self.assertEqual(row.amount_of_rfid, 2)

    def test_add_sensor_increments_atomically(self):
        DailyReaderCounter.add_sensor(self.reader)
        row = DailyReaderCounter.objects.get(number=self.reader, day=self.today)
        self.assertEqual(row.amount_of_sensor, 1)

        DailyReaderCounter.add_sensor(self.reader)
        row = DailyReaderCounter.objects.get(number=self.reader, day=self.today)
        self.assertEqual(row.amount_of_sensor, 2)

    def test_unique_constraint(self):
        # попытка создать дубль вручную должна падать
        DailyReaderCounter.objects.create(
            number=self.reader, day=self.today,
            amount_of_rfid=0, amount_of_sensor=0
        )
        with self.assertRaises(IntegrityError):
            DailyReaderCounter.objects.create(
                number=self.reader, day=self.today,
                amount_of_rfid=0, amount_of_sensor=0
            )

    def test_change_at_updates_on_increment(self):
        DailyReaderCounter.add_rfid(self.reader)
        row = DailyReaderCounter.objects.get(number=self.reader, day=self.today)
        first_changed = row.change_at
        # небольшой инкремент — метка должна обновиться
        DailyReaderCounter.add_sensor(self.reader)
        row.refresh_from_db()
        self.assertGreater(row.change_at, first_changed)
