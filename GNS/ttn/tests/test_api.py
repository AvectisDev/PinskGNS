from unittest.mock import patch

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from ttn.models import MiriadaTtn, MiriadaTtnStatus


class MiriadaTtnAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ttn_api', password='x')
        self.url = reverse('ttn_api:miriada-ttn-current')

    @patch('ttn.api.views.services.sync_current_ttn_from_miriada')
    def test_unauthenticated_returns_200(self, mock_sync):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])
        mock_sync.assert_called_once()

    @patch('ttn.api.views.services.sync_current_ttn_from_miriada')
    def test_stale_bearer_token_still_returns_200(self, mock_sync):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer not.a.valid.token')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])
        mock_sync.assert_called_once()

    @patch('ttn.api.views.services.sync_current_ttn_from_miriada')
    def test_empty_list_returns_200(self, mock_sync):
        self.client.force_authenticate(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])
        mock_sync.assert_called_once()

    @patch('ttn.api.views.services.sync_current_ttn_from_miriada')
    def test_response_includes_operation_name_and_numeric_status(self, mock_sync):
        MiriadaTtn.objects.create(
            ttn_id=56615,
            name='0567005',
            auto='AH 8918-1',
            operation_name='Отпуск в ПУ/РГС',
            date=timezone.localdate(),
            status=MiriadaTtnStatus.ERROR,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        item = response.data[0]
        self.assertEqual(item['ttn_id'], 56615)
        self.assertEqual(item['operation_name'], 'Отпуск в ПУ/РГС')
        self.assertEqual(item['status'], 2)
        self.assertEqual(item['name'], '0567005')
        self.assertEqual(item['auto'], 'AH 8918-1')

