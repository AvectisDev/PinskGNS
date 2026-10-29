from rest_framework import status
from rest_framework.test import APITestCase


class CheckConnectionTests(APITestCase):
    url = '/api/check-connection/'

    def test_unauthenticated_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_stale_bearer_token_still_returns_200(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer not.a.valid.token')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'status': 'ok'})
