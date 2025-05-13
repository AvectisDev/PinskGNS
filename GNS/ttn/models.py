from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.db.models import Q, Sum
from filling_station.models import BalloonsLoadingBatch, BalloonsUnloadingBatch, AutoGasBatch
from railway_service.models import RailwayTank


GAS_TYPE_CHOICES = [
    ('Не выбран', 'Не выбран'),
    ('СПБТ', 'СПБТ'),
    ('ПБА', 'ПБА'),
]


class Contractor(models.Model):
    name = models.CharField(max_length=200, verbose_name="Контрагент")
    code = models.CharField(max_length=20, null=True, blank=True, verbose_name="Код")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Контрагент"
        verbose_name_plural = "Контрагенты"


class City(models.Model):
    name = models.CharField(max_length=200, verbose_name="Город")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Город"
        verbose_name_plural = "Города"


class BalloonTtn(models.Model):
    number = models.CharField(blank=True, max_length=100, verbose_name="Номер ТТН")
    contract = models.CharField(blank=True, max_length=100, verbose_name="Номер договора")
    shipper = models.ForeignKey(
        Contractor,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Грузоотправитель",
        related_name='balloons_shipper'
    )
    carrier = models.ForeignKey(
        Contractor,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Перевозчик",
        related_name='balloons_carrier'
    )
    consignee = models.ForeignKey(
        Contractor,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Грузополучатель",
        related_name='balloons_consignee'
    )
    city = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Город",
        related_name='balloons_city'
    )
    loading_batch = models.ForeignKey(
        BalloonsLoadingBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Партия приёмки",
        related_name='balloons_ttn_loading'
    )
    unloading_batch = models.ForeignKey(
        BalloonsUnloadingBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Партия отгрузки",
        related_name='balloons_ttn_unloading'
    )
    date = models.DateField(null=True, blank=True, verbose_name="Дата формирования накладной")

    def __str__(self):
        return self.number

    class Meta:
        verbose_name = "Баллоны"
        verbose_name_plural = "Баллоны"
        ordering = ['-id', '-date']

    def get_batch(self):
        """Возвращает связанную партию (приёмки или отгрузки)"""
        return self.loading_batch or self.unloading_batch

    @property
    def batch_type(self):
        """Возвращает тип связанной партии ('loading', 'unloading' или None)"""
        if self.loading_batch:
            return 'loading'
        elif self.unloading_batch:
            return 'unloading'
        return None

    def get_absolute_url(self):
        return reverse('ttn:ttn_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('ttn:ttn_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('ttn:ttn_delete', args=[self.pk])


class RailwayTtn(models.Model):
    number = models.CharField(blank=False, max_length=100, verbose_name="Номер ТТН")
    railway_ttn = models.CharField(null=True, blank=True, max_length=50, verbose_name="Номер ж/д накладной")
    railway_tank_list = models.ManyToManyField(
        RailwayTank,
        blank=True,
        verbose_name="Список жд цистерн"
    )
    contract = models.CharField(blank=True, max_length=100, verbose_name="Номер договора")
    shipper = models.ForeignKey(
        Contractor,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Грузоотправитель",
        related_name='railway_tank_shipper'
    )
    carrier = models.ForeignKey(
        Contractor,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Перевозчик",
        related_name='railway_tank_carrier'
    )
    consignee = models.ForeignKey(
        Contractor,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Грузополучатель",
        related_name='railway_tank_consignee'
    )
    total_gas_amount_by_scales = models.FloatField(null=True, blank=True, verbose_name="Количество газа по весам")
    total_gas_amount_by_ttn = models.FloatField(null=True, blank=True, verbose_name="Количество газа по ТТН")
    gas_type = models.CharField(max_length=10, choices=GAS_TYPE_CHOICES, default='Не выбран', verbose_name="Тип газа")
    date = models.DateField(null=True, blank=True, verbose_name="Дата формирования накладной")

    def __str__(self):
        return self.number

    class Meta:
        verbose_name = "Железнодорожная ТТН"
        verbose_name_plural = "Железнодорожные ТТН"
        ordering = ['-id', '-date']

    def get_absolute_url(self):
        return reverse('ttn:railway_ttn_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('ttn:railway_ttn_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('ttn:railway_ttn_delete', args=[self.pk])

    def update_gas_amounts(self):
        """Обновляет суммы газа по связанным цистернам"""
        tanks = self.railway_tank_list.all()
        self.total_gas_amount_by_scales = tanks.aggregate(total=Sum('gas_weight'))['total'] or 0
        self.total_gas_amount_by_ttn = tanks.aggregate(total=Sum('netto_weight_ttn'))['total'] or 0
        self.save()


class AutoTtn(models.Model):
    number = models.CharField(blank=False, max_length=100, verbose_name="Номер ТТН")
    contract = models.CharField(blank=True, max_length=100, verbose_name="Номер договора")
    shipper = models.ForeignKey(
        Contractor,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Грузоотправитель",
        related_name='auto_tank_shipper'
    )
    carrier = models.ForeignKey(
        Contractor,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Перевозчик",
        related_name='auto_tank_carrier'
    )
    consignee = models.ForeignKey(
        Contractor,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Грузополучатель",
        related_name='auto_tank_consignee'
    )
    city = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Город",
        related_name='auto_tank_city'
    )
    batch = models.ForeignKey(
        AutoGasBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Партия",
        related_name='auto_batch_for_ttn'
    )
    total_gas_amount = models.FloatField(null=True, blank=True, verbose_name="Количество газа")
    source_gas_amount = models.CharField(max_length=20, null=True, blank=True, verbose_name="Источник веса для ТТН")
    gas_type = models.CharField(max_length=10, choices=GAS_TYPE_CHOICES, default='Не выбран', verbose_name="Тип газа")
    date = models.DateField(null=True, blank=True, verbose_name="Дата формирования накладной")

    def __str__(self):
        return self.number

    class Meta:
        verbose_name = "Автоцистерны"
        verbose_name_plural = "Автоцистерны"
        ordering = ['-id', '-date']

    def get_absolute_url(self):
        return reverse('ttn:auto_ttn_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('ttn:auto_ttn_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('ttn:auto_ttn_delete', args=[self.pk])


class FilePath(models.Model):
    path = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.path or "API"

    class Meta:
        verbose_name = "Путь сохранения файла"
        verbose_name_plural = "Путь сохранения файла"
