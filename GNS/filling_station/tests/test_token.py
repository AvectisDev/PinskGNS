from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class TokenObtainTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='mobile', password='secret')
        self.url = reverse('filling_station_api:token_obtain_pair')

    def test_obtain_without_auth_returns_tokens(self):
        response = self.client.post(
            self.url,
            {'username': 'mobile', 'password': 'secret'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_obtain_with_stale_bearer_still_returns_tokens(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer not.a.valid.token')
        response = self.client.post(
            self.url,
            {'username': 'mobile', 'password': 'secret'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
