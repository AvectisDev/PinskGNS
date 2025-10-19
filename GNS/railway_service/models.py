from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.conf import settings
from django.db.models import Count, Sum
from datetime import datetime, time


class RailwayTank(models.Model):
    registration_number = models.IntegerField(unique=True, blank=False, verbose_name="Номер ж/д цистерны")
    gas_type = models.CharField(max_length=10, choices=settings.GAS_TYPE_CHOICES, default='Не выбран', verbose_name="Тип газа")
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
    full_weight = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, verbose_name="Вес полной цистерны")
    empty_weight = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, verbose_name="Вес пустой цистерны")
    gas_weight = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, verbose_name="Поставлено газа")
    railway_ttn = models.CharField(null=True, blank=True, max_length=50, verbose_name="Номер ж/д накладной")
    netto_weight_ttn = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, verbose_name="Вес НЕТТО ж/д цистерны по накладной")
    arrival_img = models.ImageField(null=True, blank=True, upload_to='railway_tanks/', verbose_name="Фото номера при въезде")
    departure_img = models.ImageField(null=True, blank=True, upload_to='railway_tanks/', verbose_name="Фото номера при выезде")
    

    class Meta:
        verbose_name = "История цистерны"
        verbose_name_plural = "Истории цистерн"
        ordering = ['-arrival_at', '-departure_at']

    def __str__(self):
        return f"{self.tank.registration_number}: {self.arrival_at} → {self.departure_at}"


class RailwayBatch(models.Model):
    begin_date = models.DateTimeField(auto_now_add=True, verbose_name="Дата начала приёмки")
    end_date = models.DateTimeField(null=True, blank=True, verbose_name="Дата окончания приёмки")
    gas_amount_spbt = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, verbose_name="Количество принятого СПБТ газа")
    gas_amount_pba = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, verbose_name="Количество принятого ПБА газа")
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

    @classmethod
    def get_period_stats(cls, start_date, end_date):
        start_datetime = datetime.combine(start_date, time.min)
        end_datetime = datetime.combine(end_date, time.max)
        return cls.objects.filter(
            begin_date__range=[start_datetime, end_datetime]
        ).annotate(
            tanks_count=Count('railway_tank_list'),
            total_gas_in_tanks=Sum('railway_tank_list__tank_history__gas_weight')
        ).aggregate(
            total_batches=Count('id'),
            total_tanks=Sum('tanks_count'),
            total_gas_spbt=Sum('gas_amount_spbt'),
            total_gas_pba=Sum('gas_amount_pba'),
            total_gas_in_all_tanks=Sum('total_gas_in_tanks')
        )
