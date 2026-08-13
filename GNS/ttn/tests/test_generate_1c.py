import os
import tempfile
from datetime import datetime
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from filling_station.models import BalloonsBatch
from ttn.management.commands.generate_1c_file import Command
from ttn.models import BalloonTtn, FilePath, RailwayTtn
from .helpers import TtnFixturesMixin


class Generate1cFileTests(TtnFixturesMixin, TestCase):
    def test_balloon_loading_uses_related_name(self):
        batch = BalloonsBatch.objects.create(
            batch_type='l',
            truck=self.truck,
            ttn_id=300,
            user=self.user,
            amount_of_50_liters=4,
        )
        BalloonTtn.objects.create(number='BAL-77', loading_batch=batch)
        content = Command().generate_balloon_loading_list(timezone.now())
        self.assertIn('ГНС-ТТН4', content)
        self.assertIn('BAL-77', content)
        self.assertIn('Баллоны 50 л', content)

    def test_balloon_unloading_uses_related_name(self):
        batch = BalloonsBatch.objects.create(
            batch_type='u',
            truck=self.truck,
            ttn_id=301,
            user=self.user,
            amount_of_27_liters=2,
        )
        BalloonTtn.objects.create(number='BAL-88', unloading_batch=batch)
        content = Command().generate_balloon_unloading_list(timezone.now())
        self.assertIn('ГНС-ТТН5', content)
        self.assertIn('BAL-88', content)

    def test_filename_uses_handle_date_not_class_attr(self):
        self.assertFalse(isinstance(getattr(Command, 'today', None), str))
        fixed = timezone.make_aware(datetime(2024, 12, 31, 12, 0, 0))
        with tempfile.TemporaryDirectory() as tmpdir:
            FilePath.objects.create(path=tmpdir)
            with patch(
                'ttn.management.commands.generate_1c_file.timezone.now',
                return_value=fixed,
            ), patch.object(Command, 'send_email_with_attachment'):
                Command().handle(ttn_number='X-1')
            expected = os.path.join(tmpdir, 'ГНС31.12.24.txt')
            self.assertTrue(os.path.exists(expected), os.listdir(tmpdir))

    def test_duplicate_railway_number_uses_latest(self):
        RailwayTtn.objects.create(number='DUP-1')
        latest = RailwayTtn.objects.create(number='DUP-1')
        latest.railway_tank_list.add(self.tank)
        content = Command().generate_railway_list('DUP-1')
        self.assertIn('DUP-1', content)

    def test_empty_filepath_does_not_write_file(self):
        FilePath.objects.create(path='')
        with self.assertLogs('celery', level='WARNING') as logs:
            Command().handle(ttn_number='X-1')
        self.assertTrue(any('FilePath' in message for message in logs.output))
