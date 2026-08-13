from django.test import Client, TestCase
from django.urls import reverse

from autogas.models import AutoGasBatchSettings
from .helpers import TtnFixturesMixin


class UpdateWeightSourceTests(TtnFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.url = reverse('ttn:update_weight_source')
        self.list_url = reverse('ttn:auto_ttn_list')

    def _csrf_token(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'csrfmiddlewaretoken')
        return self.client.cookies['csrftoken'].value

    def test_post_with_csrf_updates_source(self):
        csrf = self._csrf_token()
        response = self.client.post(
            self.url,
            {'weight_source': 's', 'csrfmiddlewaretoken': csrf},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.list_url)
        self.assertEqual(AutoGasBatchSettings.objects.get().weight_source, 's')

    def test_post_without_csrf_is_forbidden(self):
        self._csrf_token()
        response = self.client.post(self.url, {'weight_source': 'f'})
        self.assertEqual(response.status_code, 403)
