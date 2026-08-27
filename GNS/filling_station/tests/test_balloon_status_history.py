from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from filling_station.models import Balloon
from filling_station.views import BALLOON_STATUS_HISTORY_PAGE_SIZE


class BalloonStatusHistoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='history_user', password='x')
        self.balloon = Balloon.objects.create(
            nfc_tag='historytag01',
            serial_number='SN-HIST-01',
            status='Новый',
            user=self.user,
        )

    def _create_history_entries(self, count: int) -> None:
        for index in range(count):
            self.balloon.status = f'Статус {index}'
            self.balloon.save()

    def test_detail_shows_status_history_block(self):
        self._create_history_entries(2)
        url = reverse('filling_station:balloon_detail', args=[self.balloon.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'историю статусов')
        self.assertContains(response, 'Статус 1')

    def test_status_history_endpoint_returns_next_page(self):
        self._create_history_entries(BALLOON_STATUS_HISTORY_PAGE_SIZE + 2)
        url = reverse('filling_station:balloon_status_history', args=[self.balloon.pk])

        response = self.client.get(url, {'offset': BALLOON_STATUS_HISTORY_PAGE_SIZE})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Статус 1')
        self.assertContains(response, 'Статус 0')
        self.assertNotContains(response, f'Статус {BALLOON_STATUS_HISTORY_PAGE_SIZE + 1}')

    def test_status_history_endpoint_returns_empty_when_exhausted(self):
        self._create_history_entries(1)
        url = reverse('filling_station:balloon_status_history', args=[self.balloon.pk])

        response = self.client.get(url, {'offset': BALLOON_STATUS_HISTORY_PAGE_SIZE})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.strip(), b'')
