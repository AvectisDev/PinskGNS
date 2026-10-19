from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from filling_station.models import Balloon


class BalloonPartialUpdateTests(APITestCase):
    def setUp(self):
        try:
            self.user = User.objects.get(pk=1)
        except User.DoesNotExist:
            self.user = User.objects.create_user(id=1, username='balloon_api', password='x')
        self.client.force_authenticate(self.user)
        self.balloon = Balloon.objects.create(
            nfc_tag='04bf9124cf201de0',
            serial_number='S123',
            status='Создание паспорта баллона',
        )

    def test_patch_status_keeps_nfc_tag(self):
        url = reverse('filling_station_api:balloons-detail', args=[self.balloon.nfc_tag])
        response = self.client.patch(url, {'status': 'Покраска'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nfc_tag'], '04bf9124cf201de0')
        self.assertEqual(response.data['status'], 'Покраска')
        self.balloon.refresh_from_db()
        self.assertEqual(self.balloon.nfc_tag, '04bf9124cf201de0')
        self.assertEqual(self.balloon.status, 'Покраска')
        self.assertTrue(Balloon.objects.filter(nfc_tag='04bf9124cf201de0').exists())
        self.assertFalse(Balloon.objects.filter(nfc_tag='').exists())

    def test_patch_with_same_nfc_tag_updates_fields(self):
        url = reverse('filling_station_api:balloons-detail', args=[self.balloon.nfc_tag])
        response = self.client.patch(
            url,
            {'nfc_tag': self.balloon.nfc_tag, 'status': 'Покраска'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nfc_tag'], '04bf9124cf201de0')
        self.balloon.refresh_from_db()
        self.assertEqual(self.balloon.status, 'Покраска')

    def test_patch_changes_nfc_tag(self):
        url = reverse('filling_station_api:balloons-detail', args=[self.balloon.nfc_tag])
        response = self.client.patch(
            url,
            {'nfc_tag': 'aabbccddeeff0011', 'status': 'Покраска'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nfc_tag'], 'aabbccddeeff0011')
        self.assertFalse(Balloon.objects.filter(nfc_tag='04bf9124cf201de0').exists())
        self.assertTrue(Balloon.objects.filter(nfc_tag='aabbccddeeff0011').exists())
