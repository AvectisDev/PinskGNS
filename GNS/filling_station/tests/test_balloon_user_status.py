from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from filling_station.models import BalloonUserStatus

# Ожидаемый порядок после data-миграции 0028_seed_balloon_user_status.
SEEDED_STATUS_NAMES = [
    'Создание паспорта баллона',
    'Наполнение баллона сжиженным газом',
    'Погрузка полного баллона в кассету',
    'Погрузка полного баллона в трал',
    'Погрузка пустого баллона в кассету',
    'Погрузка пустого баллона в трал',
    'Регистрация полного баллона на складе',
    'Регистрация пустого баллона на складе',
    'Снятие пустого баллона у потребителя',
    'Установка баллона потребителю',
    'Принятие баллона от другой организации',
    'Снятие RFID метки',
    'Установка новой RFID метки',
    'Редактирование паспорта баллона',
    'Покраска',
    'Техническое освидетельствование',
    'Выбраковка',
    'Утечка газа',
    'Опорожнение(слив) баллона',
    'Контрольное взвешивание',
]


class BalloonUserStatusTests(APITestCase):
    def setUp(self):
        try:
            self.user = User.objects.get(pk=1)
        except User.DoesNotExist:
            self.user = User.objects.create_user(id=1, username='status_operator', password='x')
        self.client.force_authenticate(self.user)

    def test_seed_contains_expected_statuses(self):
        names = BalloonUserStatus.active_names()
        self.assertEqual(names, SEEDED_STATUS_NAMES)
        self.assertEqual(BalloonUserStatus.objects.count(), len(SEEDED_STATUS_NAMES))

    def test_status_options_endpoint_returns_active_names(self):
        url = reverse('filling_station_api:balloon-status-options')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, SEEDED_STATUS_NAMES)

    def test_inactive_status_excluded_from_api(self):
        inactive = BalloonUserStatus.objects.get(name='Покраска')
        inactive.is_active = False
        inactive.save(update_fields=['is_active'])

        url = reverse('filling_station_api:balloon-status-options')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('Покраска', response.data)
        self.assertEqual(
            response.data,
            [name for name in SEEDED_STATUS_NAMES if name != 'Покраска'],
        )
