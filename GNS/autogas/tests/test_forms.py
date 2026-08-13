from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from autogas.forms import AutoGasBatchForm
from .helpers import AutoGasFixturesMixin


class AutoGasBatchFormTests(AutoGasFixturesMixin, TestCase):
    def _form(self, extra=None, instance=None):
        data = {
            'batch_type': 'l',
            'truck': self.truck.pk,
            'gas_type': 'СПБТ',
            'is_active': False,
        }
        if extra:
            data.update(extra)
        return AutoGasBatchForm(data=data, instance=instance)

    def test_rejects_completed_at_before_begin_at(self):
        batch = self.make_batch()
        too_early = timezone.localtime(batch.begin_at) - timedelta(hours=1)
        form = self._form(
            extra={'completed_at': too_early.strftime('%Y-%m-%dT%H:%M')},
            instance=batch,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('completed_at', form.errors)

    def test_rejects_second_active_batch(self):
        self.make_batch(is_active=True)
        form = self._form(extra={'is_active': True})
        self.assertFalse(form.is_valid())
        self.assertIn('is_active', form.errors)

    def test_rejects_full_weight_not_greater_than_empty(self):
        form = self._form(extra={
            'scale_empty_weight': '10',
            'scale_full_weight': '10',
        })
        self.assertFalse(form.is_valid())

    def test_rejects_weight_mismatch(self):
        form = self._form(extra={
            'scale_empty_weight': '10',
            'scale_full_weight': '20',
            'weight_gas_amount': '5',
        })
        self.assertFalse(form.is_valid())

    def test_accepts_matching_weights(self):
        form = self._form(extra={
            'scale_empty_weight': '10',
            'scale_full_weight': '20.05',
            'weight_gas_amount': '10',
        })
        self.assertTrue(form.is_valid(), form.errors)
