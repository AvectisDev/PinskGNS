from datetime import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from filling_station.models import BalloonsBatch, Truck, TruckType
from ttn.models import MiriadaTtn


class BalloonBatchListFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='batch_filter_user', password='x')
        self.truck_type = TruckType.objects.create(type='Трал')
        self.truck = Truck.objects.create(
            registration_number='AM5448-1',
            type=self.truck_type,
            car_brand='МАЗ',
        )
        self.other_truck = Truck.objects.create(
            registration_number='BC1111-2',
            type=self.truck_type,
            car_brand='Volvo',
        )
        MiriadaTtn.objects.create(ttn_id=100, name='TTN-100')
        MiriadaTtn.objects.create(ttn_id=200, name='TTN-200')
        MiriadaTtn.objects.create(ttn_id=300, name='4078183')

        self.today = timezone.localdate()
        self.batch_today = self._create_batch(
            self.truck,
            ttn_id=100,
            started_at=timezone.make_aware(datetime.combine(self.today, datetime.min.time())),
        )
        self.batch_old = self._create_batch(
            self.other_truck,
            ttn_id=200,
            started_at=timezone.make_aware(datetime(2020, 1, 1, 10, 0)),
        )

    def _create_batch(self, truck, ttn_id, started_at):
        batch = BalloonsBatch.objects.create(
            batch_type='l',
            truck=truck,
            ttn_id=ttn_id,
            reader_number=1,
            user=self.user,
        )
        BalloonsBatch.objects.filter(pk=batch.pk).update(started_at=started_at)
        return batch

    def _get_ids(self, **params):
        url = reverse('filling_station:balloon_loading_batch_list')
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        return set(response.context['page_obj'].object_list.values_list('id', flat=True))

    def test_shows_all_batches_without_date_filter(self):
        ids = self._get_ids()
        self.assertEqual(ids, {self.batch_today.id, self.batch_old.id})

    def test_filters_by_date_range(self):
        ids = self._get_ids(
            start_date=self.today.isoformat(),
            end_date=self.today.isoformat(),
        )
        self.assertIn(self.batch_today.id, ids)
        self.assertNotIn(self.batch_old.id, ids)

    def test_filters_by_truck_number_without_date_filter(self):
        ids = self._get_ids(query='AM5448')
        self.assertEqual(ids, {self.batch_today.id})

    def test_filters_by_truck_number(self):
        ids = self._get_ids(
            start_date='2020-01-01',
            end_date=self.today.isoformat(),
            query='AM5448',
        )
        self.assertEqual(ids, {self.batch_today.id})

    def test_filters_by_ttn_number(self):
        ids = self._get_ids(
            start_date='2020-01-01',
            end_date=self.today.isoformat(),
            query='TTN-200',
        )
        self.assertEqual(ids, {self.batch_old.id})

    def test_query_filter_label_for_ttn(self):
        response = self.client.get(
            reverse('filling_station:balloon_loading_batch_list'),
            {'query': '4078183'},
        )
        self.assertEqual(response.context['query_filter']['label'], 'Фильтр по номеру ТТН')
        self.assertEqual(response.context['query_filter']['value'], '4078183')

    def test_query_filter_label_for_truck(self):
        response = self.client.get(
            reverse('filling_station:balloon_loading_batch_list'),
            {'query': 'AM5448'},
        )
        self.assertEqual(response.context['query_filter']['label'], 'Фильтр по номеру грузовика')
        self.assertEqual(response.context['query_filter']['value'], 'AM5448')
