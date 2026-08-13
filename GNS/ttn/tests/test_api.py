from unittest.mock import patch

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class MiriadaTtnAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ttn_api', password='x')
        self.url = reverse('ttn_api:miriada-ttn-current')

    def test_unauthenticated_returns_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('ttn.api.views.services.sync_current_ttn_from_miriada')
    def test_empty_list_returns_200(self, mock_sync):
        self.client.force_authenticate(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])
        mock_sync.assert_called_once()
