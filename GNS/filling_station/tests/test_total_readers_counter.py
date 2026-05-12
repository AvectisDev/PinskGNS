from django.test import TestCase
from filling_station.models import TotalReadersCounter


class TotalReadersCounterTests(TestCase):
    def setUp(self):
        # создаём запись-синглтон (если её нет)
        self.obj, _ = TotalReadersCounter.objects.get_or_create(pk=1, defaults={
            'total_empty': 0, 'total_full': 0
        })

    def test_add_full_balloon(self):
        TotalReadersCounter.add_full_balloon()
        self.obj.refresh_from_db()
        self.assertEqual(self.obj.total_full, 1)

    def test_add_empty_balloon(self):
        TotalReadersCounter.add_empty_balloon()
        self.obj.refresh_from_db()
        self.assertEqual(self.obj.total_empty, 1)

    def test_sub_full_balloon_not_below_zero(self):
        # сначала 0 → декремент не должен уходить в минус
        TotalReadersCounter.sub_full_balloon()
        self.obj.refresh_from_db()
        self.assertEqual(self.obj.total_full, 0)
        # добавим, затем вычтем
        TotalReadersCounter.add_full_balloon()
        TotalReadersCounter.sub_full_balloon()
        self.obj.refresh_from_db()
        self.assertEqual(self.obj.total_full, 0)

    def test_sub_empty_balloon_not_below_zero(self):
        TotalReadersCounter.sub_empty_balloon()
        self.obj.refresh_from_db()
        self.assertEqual(self.obj.total_empty, 0)

    def test_insert_manual_values(self):
        # ручной ввод: пустые = 25, полные = 7
        TotalReadersCounter.insert_manual_values(empty=25, full=7)
        self.obj.refresh_from_db()
        self.assertEqual(self.obj.total_empty, 25)
        self.assertEqual(self.obj.total_full, 7)

    def test_changed_at_updates(self):
        prev = self.obj.changed_at
        TotalReadersCounter.add_full_balloon()
        self.obj.refresh_from_db()
        self.assertGreater(self.obj.changed_at, prev)
