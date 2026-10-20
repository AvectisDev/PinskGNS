"""Тесты prepare_payload_for_miriada и записи ошибки Мириады на баллон."""

from unittest.mock import patch

from django.test import TestCase, override_settings

from filling_station.exceptions import MiriadaAPIError
from filling_station.models import BatchStatus
from filling_station.services.batches import add_balloon_to_batch_by_nfc
from filling_station.services.miriada import prepare_payload_for_miriada
from filling_station.tests.factories import (
    make_balloon,
    make_batch,
    make_reader,
    make_truck,
    make_user,
)


class PreparePayloadForMiriadaTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.truck = make_truck(registration_number='AC 5512-1', type_name='Трал')
        self.nfc = 'aabbccdde0'
        self.balloon = make_balloon(nfc_tag=self.nfc)

    def test_reader_4_unloading_batch_uses_loading_into_truck(self):
        make_reader(4, function='u')
        batch = make_batch(
            batch_type='u',
            truck=self.truck,
            reader_number=4,
            ttn_id=57097,
            user=self.user,
        )
        url, payload, send_type = prepare_payload_for_miriada(4, self.nfc, batch=batch)
        self.assertEqual(send_type, 'loading_into_truck')
        self.assertIn('/balloontocar', url)
        self.assertEqual(payload['nfctag'], self.nfc)
        self.assertEqual(payload['number_auto'], 'AC 5512-1')
        self.assertEqual(payload['type_car'], 1)
        self.assertEqual(payload['fulness'], 1)
        self.assertEqual(payload['id_ttn'], 57097)

    def test_reader_3_cage_truck_type_car_zero(self):
        truck = make_truck(registration_number='AP 1852-1', type_name='Клетевоз')
        batch = make_batch(
            batch_type='u',
            truck=truck,
            reader_number=3,
            user=self.user,
        )
        _, payload, send_type = prepare_payload_for_miriada(3, self.nfc, batch=batch)
        self.assertEqual(send_type, 'loading_into_truck')
        self.assertEqual(payload['type_car'], 0)
        self.assertEqual(payload['number_auto'], 'AP 1852-1')

    def test_reader_6_loading_empty_balloons_balloontosklad(self):
        make_reader(6, function='l')
        batch = make_batch(
            batch_type='l',
            truck=self.truck,
            reader_number=6,
            balloons_type='e',
            ttn_id=56946,
            user=self.user,
        )
        url, payload, send_type = prepare_payload_for_miriada(6, self.nfc, batch=batch)
        self.assertEqual(send_type, 'registering_in_warehouse')
        self.assertIn('/balloontosklad', url)
        self.assertEqual(payload['fulness'], 0)
        self.assertEqual(payload['id_ttn'], 56946)
        self.assertNotIn('number_auto', payload)

    def test_reader_6_full_balloons_fulness_one(self):
        batch = make_batch(
            batch_type='l',
            truck=self.truck,
            reader_number=6,
            balloons_type='f',
            user=self.user,
        )
        _, payload, _ = prepare_payload_for_miriada(6, self.nfc, batch=batch)
        self.assertEqual(payload['fulness'], 1)

    def test_reader_8_filling_without_batch_fields(self):
        url, payload, send_type = prepare_payload_for_miriada(8, self.nfc)
        self.assertEqual(send_type, 'filling')
        self.assertIn('/fillingballoon', url)
        self.assertEqual(payload, {'nfctag': self.nfc, 'realm': 'brestoblgas'})

    def test_unknown_reader_raises(self):
        with self.assertRaises(ValueError) as ctx:
            prepare_payload_for_miriada(99, self.nfc)
        self.assertIn('Неизвестный номер считывателя', str(ctx.exception))

    def test_loading_without_truck_raises(self):
        from unittest.mock import MagicMock

        batch = MagicMock()
        batch.id = 1
        batch.batch_type = 'u'
        batch.truck = None
        batch.ttn_id = 57097
        with self.assertRaises(ValueError) as ctx:
            prepare_payload_for_miriada(4, self.nfc, batch=batch)
        self.assertIn('грузовике', str(ctx.exception))

    def test_loading_without_active_batch_for_nfc_raises(self):
        with self.assertRaises(ValueError) as ctx:
            prepare_payload_for_miriada(4, self.nfc, batch=None)
        self.assertIn('Не найдена активная партия отгрузки', str(ctx.exception))


@override_settings(MIRIADA_REQUEST_RETRIES=0, MIRIADA_RETRY_DELAY_SECONDS=0)
class AddBalloonStoresHumanReadableMiriadaErrorTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.truck = make_truck(registration_number='AP 1852-1')
        make_reader(4, function='u')
        self.batch = make_batch(
            batch_type='u',
            truck=self.truck,
            reader_number=4,
            amount_of_ttn=10,
            user=self.user,
        )
        self.balloon = make_balloon(nfc_tag='carnotfound01e0')

    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_add_balloon_stores_description_not_raw_json(self, mock_post):
        mock_post.side_effect = MiriadaAPIError('Автомобиль не найден')
        result = add_balloon_to_batch_by_nfc(self.batch, self.balloon.nfc_tag)
        self.assertTrue(result['success'])
        self.balloon.refresh_from_db()
        self.assertEqual(self.balloon.miriada_status_error, 'Автомобиль не найден')
        self.assertNotIn('{', self.balloon.miriada_status_error)
        self.batch.refresh_from_db()
        self.assertEqual(
            self.batch.miriada_status_errors[self.balloon.nfc_tag],
            'Автомобиль не найден',
        )
