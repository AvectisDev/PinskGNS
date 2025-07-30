from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.db.models import Q, Sum, Count
from django.conf import settings
from filling_station.models import Truck, Trailer


BATCH_TYPE_CHOICES = [
    ('l', 'Приёмка'),
    ('u', 'Отгрузка'),
]


class AutoGasBatch(models.Model):
    batch_type = models.CharField(max_length=10, choices=BATCH_TYPE_CHOICES, default='u', verbose_name="Тип партии")
    begin_date = models.DateField(null=True, blank=True, verbose_name="Дата начала приёмки")
    begin_time = models.TimeField(null=True, blank=True, verbose_name="Время начала приёмки")
    end_date = models.DateField(null=True, blank=True, verbose_name="Дата окончания приёмки")
    end_time = models.TimeField(null=True, blank=True, verbose_name="Время окончания приёмки")
    truck = models.ForeignKey(
        Truck,
        on_delete=models.DO_NOTHING,
        verbose_name="Автомобиль"
    )
    trailer = models.ForeignKey(
        Trailer,
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        default=0,
        verbose_name="Прицеп"
    )
    gas_amount = models.FloatField(null=True, blank=True, verbose_name="Количество газа (массомер)")
    gas_type = models.CharField(max_length=10, choices=settings.GAS_TYPE_CHOICES, default='Не выбран', verbose_name="Тип газа")
    scale_empty_weight = models.FloatField(null=True, blank=True, verbose_name="Вес пустого т/с (весы)")
    scale_full_weight = models.FloatField(null=True, blank=True, verbose_name="Вес полного т/с (весы)")
    weight_gas_amount = models.FloatField(null=True, blank=True, verbose_name="Количество газа (весы)")
    is_active = models.BooleanField(null=True, blank=True, verbose_name="В работе")
    user = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        default=1,
        verbose_name="Пользователь"
    )

    def __str__(self):
        return str(self.id)

    class Meta:
        verbose_name = "Автоколонка"
        verbose_name_plural = "Автоколонка"
        ordering = ['-begin_date', '-begin_time']
        app_label = 'autogas'

    def get_absolute_url(self):
        return reverse('autogas:auto_gas_batch_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('autogas:auto_gas_batch_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('autogas:auto_gas_batch_delete', args=[self.pk])

    @classmethod
    def get_period_stats(cls, start_date=None, end_date=None):
        queryset = cls.objects.filter(begin_date__range=[start_date, end_date])

        return queryset.aggregate(
            loading_batches=Count('id', filter=Q(batch_type='l')),
            unloading_batches=Count('id', filter=Q(batch_type='u')),
            total_gas_loading_by_weight=Sum('weight_gas_amount', filter=Q(batch_type='l')),
            total_gas_loading_by_flowmeter=Sum('gas_amount', filter=Q(batch_type='l')),
            total_gas_unloading_by_weight=Sum('weight_gas_amount', filter=Q(batch_type='u')),
            total_gas_unloading_by_flowmeter = Sum('gas_amount', filter=Q(batch_type='u')),
        )


WEIGHT_SOURCE_CHOICES = [
    ('f', 'Расходомер'),
    ('s', 'Весы'),
]


class AutoGasBatchSettings(models.Model):
    weight_source = models.CharField(choices=WEIGHT_SOURCE_CHOICES, default='f', verbose_name="Источник веса для ТТН")

    def __str__(self):
        return 'Настройки автоколонки'

    class Meta:
        verbose_name = "Настройки автоколонки"
        verbose_name_plural = "Настройки автоколонки"
