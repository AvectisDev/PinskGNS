from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.conf import settings
from django.db.models import Count, Prefetch


class RailwayTank(models.Model):
    registration_number = models.IntegerField(unique=True, blank=False, verbose_name="Номер ж/д цистерны")
    is_on_station = models.BooleanField(default=False, verbose_name="Находится на станции")
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        default=1,
        verbose_name="Пользователь"
    )

    def __str__(self):
        return str(self.registration_number)


    class Meta:
        verbose_name = "Ж/д цистерна"
        verbose_name_plural = "Ж/д цистерны"
        ordering = ['-is_on_station']

    def get_absolute_url(self):
        return reverse('railway_service:railway_tank_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('railway_service:railway_tank_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('railway_service:railway_tank_delete', args=[self.pk])

    def generate_filename(self, filename):
        # Возвращаем только имя файла без дополнительных символов для сохранения пути к фото
        return f"{self.registration_number}.jpg"


class RailwayTankHistory(models.Model):
    """История нахождения цистерны на объекте и поставок газа"""
    tank = models.ForeignKey(
        RailwayTank,
        on_delete=models.CASCADE,
        related_name='tank_history',
        verbose_name="Цистерна",
    )
    arrival_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата въезда")
    departure_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата выезда")
    full_weight = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Вес полной цистерны")
    empty_weight = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Вес пустой цистерны")
    gas_weight = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Поставлено газа")
    gas_type = models.CharField(max_length=10, choices=settings.GAS_TYPE_CHOICES, default='СПБТ', verbose_name="Тип газа")
    railway_ttn = models.CharField(null=True, blank=True, max_length=50, verbose_name="Номер ж/д накладной")
    netto_weight_ttn = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Вес НЕТТО ж/д цистерны по накладной")
    arrival_img = models.ImageField(null=True, blank=True, upload_to='railway_tanks/', verbose_name="Фото номера при въезде")
    departure_img = models.ImageField(null=True, blank=True, upload_to='railway_tanks/', verbose_name="Фото номера при выезде")
    

    class Meta:
        verbose_name = "История цистерны"
        verbose_name_plural = "Истории цистерн"
        ordering = ['-arrival_at']

    def __str__(self):
        return f"{self.tank.registration_number}: {self.arrival_at} → {self.departure_at}"


class RailwayBatch(models.Model):
    begin_date = models.DateTimeField(auto_now_add=True, verbose_name="Дата начала приёмки")
    end_date = models.DateTimeField(null=True, blank=True, verbose_name="Дата окончания приёмки")
    gas_amount_spbt = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Количество принятого СПБТ газа")
    gas_amount_pba = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Количество принятого ПБА газа")
    railway_tank_list = models.ManyToManyField(
        RailwayTank,
        blank=True,
        verbose_name="Список жд цистерн"
    )
    is_active = models.BooleanField(default=False, verbose_name="В работе")
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        default=1,
        verbose_name="Пользователь"
    )

    class Meta:
        verbose_name = "Партия приёмки жд цистерн"
        verbose_name_plural = "Партии приёмки жд цистерн"
        ordering = ['-begin_date']

    def get_absolute_url(self):
        return reverse('railway_service:railway_batch_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('railway_service:railway_batch_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('railway_service:railway_batch_delete', args=[self.pk])

    def get_gas_totals(self) -> dict:
        """Суммы газа по последней истории цистерн партии.

        Если у части цистерн нет веса газа, сумма считается по имеющимся
        данным и помечается как неполная.
        """
        empty = {'amount': Decimal('0'), 'incomplete': False, 'has_tanks': False}
        totals = {
            'spbt': dict(empty),
            'pba': dict(empty),
        }
        key_by_type = {'СПБТ': 'spbt', 'ПБА': 'pba'}

        for tank in self.railway_tank_list.all():
            last = next(iter(tank.tank_history.all()), None)
            gas_type = last.gas_type if last and last.gas_type else 'СПБТ'
            bucket = totals[key_by_type.get(gas_type, 'spbt')]
            bucket['has_tanks'] = True
            if last is None or last.gas_weight is None:
                bucket['incomplete'] = True
                continue
            bucket['amount'] += last.gas_weight

        return totals

    @classmethod
    def get_period_stats(cls, start_date, end_date):
        tank_history = Prefetch(
            'tank_history',
            queryset=RailwayTankHistory.objects.order_by('-arrival_at'),
        )
        queryset = cls.objects.filter(
            begin_date__date__gte=start_date,
            begin_date__date__lte=end_date,
        ).prefetch_related(
            Prefetch(
                'railway_tank_list',
                queryset=RailwayTank.objects.prefetch_related(tank_history),
            )
        )

        aggregate_stats = queryset.aggregate(
            total_batches=Count('id'),
            total_tanks=Count('railway_tank_list', distinct=True),
        )

        total_gas_spbt = Decimal('0')
        total_gas_pba = Decimal('0')
        spbt_incomplete = False
        pba_incomplete = False
        has_spbt = False
        has_pba = False

        for batch in queryset:
            totals = batch.get_gas_totals()
            if totals['spbt']['has_tanks']:
                has_spbt = True
                total_gas_spbt += totals['spbt']['amount']
                if totals['spbt']['incomplete']:
                    spbt_incomplete = True
            if totals['pba']['has_tanks']:
                has_pba = True
                total_gas_pba += totals['pba']['amount']
                if totals['pba']['incomplete']:
                    pba_incomplete = True

        return {
            'total_batches': aggregate_stats['total_batches'] or 0,
            'total_tanks': aggregate_stats['total_tanks'] or 0,
            'total_gas_spbt': total_gas_spbt,
            'total_gas_pba': total_gas_pba,
            'total_gas_in_all_tanks': total_gas_spbt + total_gas_pba,
            'spbt_incomplete': spbt_incomplete,
            'pba_incomplete': pba_incomplete,
            'has_spbt': has_spbt,
            'has_pba': has_pba,
        }
