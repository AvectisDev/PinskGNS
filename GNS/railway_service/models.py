from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.conf import settings


class RailwayTank(models.Model):
    registration_number = models.CharField(blank=False, max_length=20, verbose_name="Номер ж/д цистерны")
    empty_weight = models.FloatField(null=True, blank=True, verbose_name="Вес пустой цистерны")
    full_weight = models.FloatField(null=True, blank=True, verbose_name="Вес полной цистерны")
    gas_weight = models.FloatField(null=True, blank=True, verbose_name="Масса перевозимого газа")
    gas_type = models.CharField(max_length=10, choices=settings.GAS_TYPE_CHOICES, default='Не выбран', verbose_name="Тип газа")
    is_on_station = models.BooleanField(null=True, blank=True, verbose_name="Находится на станции")
    railway_ttn = models.CharField(null=True, blank=True, max_length=50, verbose_name="Номер ж/д накладной")
    netto_weight_ttn = models.FloatField(null=True, blank=True, verbose_name="Вес НЕТТО ж/д цистерны по накладной")
    entry_date = models.DateField(null=True, blank=True, verbose_name="Дата въезда")
    entry_time = models.TimeField(null=True, blank=True, verbose_name="Время въезда")
    departure_date = models.DateField(null=True, blank=True, verbose_name="Дата выезда")
    departure_time = models.TimeField(null=True, blank=True, verbose_name="Время выезда")
    registration_number_img = models.ImageField(null=True, blank=True, upload_to='railway_tanks/', verbose_name="Фото номера")
    user = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        default=1,
        verbose_name="Пользователь"
    )

    def __str__(self):
        return self.registration_number

    class Meta:
        verbose_name = "Ж/д цистерна"
        verbose_name_plural = "Ж/д цистерны"
        ordering = ['-is_on_station', '-entry_date', '-entry_time', '-departure_date', '-departure_time']

    def get_absolute_url(self):
        return reverse('railway_service:railway_tank_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('railway_service:railway_tank_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('railway_service:railway_tank_delete', args=[self.pk])

    def generate_filename(self, filename):
        # Возвращаем только имя файла без дополнительных символов для сохранения пути к фото
        return f"{self.registration_number}.jpg"


class RailwayBatch(models.Model):
    begin_date = models.DateTimeField(auto_now_add=True, verbose_name="Дата начала приёмки")
    end_date = models.DateTimeField(null=True, blank=True, verbose_name="Дата окончания приёмки")
    gas_amount_spbt = models.FloatField(null=True, blank=True, verbose_name="Количество принятого СПБТ газа")
    gas_amount_pba = models.FloatField(null=True, blank=True, verbose_name="Количество принятого ПБА газа")
    railway_tank_list = models.ManyToManyField(
        RailwayTank,
        blank=True,
        verbose_name="Список жд цистерн"
    )
    is_active = models.BooleanField(null=True, blank=True, verbose_name="В работе")
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
