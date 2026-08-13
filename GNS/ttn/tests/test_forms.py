from decimal import Decimal

from django.test import TestCase

from filling_station.models import BalloonsBatch
from autogas.models import AutoGasBatchSettings
from ttn.forms import AutoTtnForm, BalloonTtnForm
from .helpers import TtnFixturesMixin


class AutoTtnFormCleanTests(TtnFixturesMixin, TestCase):
    def _form(self, batch):
        return AutoTtnForm(data={
            'number': 'A-1',
            'batch': batch.pk,
            'shipper': self.contractor.pk,
            'carrier': self.contractor.pk,
            'consignee': self.contractor.pk,
            'city': self.city.pk,
        })

    def test_rejects_missing_flowmeter_amount(self):
        AutoGasBatchSettings.objects.create(weight_source='f')
        batch = self.make_auto_batch(gas_amount=None)
        form = self._form(batch)
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_rejects_missing_scale_amount(self):
        AutoGasBatchSettings.objects.create(weight_source='s')
        batch = self.make_auto_batch(weight_gas_amount=None)
        form = self._form(batch)
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_rejects_missing_gas_type(self):
        AutoGasBatchSettings.objects.create(weight_source='f')
        batch = self.make_auto_batch(gas_amount=Decimal('10'), gas_type='')
        form = self._form(batch)
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_accepts_batch_with_flowmeter_amount(self):
        AutoGasBatchSettings.objects.create(weight_source='f')
        batch = self.make_auto_batch(gas_amount=Decimal('10'))
        form = self._form(batch)
        self.assertTrue(form.is_valid(), form.errors)


class BalloonTtnFormChoiceTests(TtnFixturesMixin, TestCase):
    def test_unloading_batch_labeled_as_unloading(self):
        batch = BalloonsBatch.objects.create(
            batch_type='u',
            truck=self.truck,
            ttn_id=200,
            user=self.user,
        )
        form = BalloonTtnForm()
        label = str(form.format_batch_choice(batch))
        self.assertIn('Отгрузка', label)
        self.assertNotIn('Приёмка', label)
