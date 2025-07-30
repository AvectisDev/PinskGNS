from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.urls import reverse
from django.db.models import Q, Sum, Count
from django.conf import settings
import pghistory


BALLOON_SIZE_CHOICES = [
    (5, 5),
    (12, 12),
    (27, 27),
    (50, 50),
]


@pghistory.track(exclude=['filling_status', 'update_passport_required'])
class Balloon(models.Model):
    nfc_tag = models.CharField(primary_key=True,max_length=30, db_index=True, verbose_name="Номер метки")
    serial_number = models.CharField(null=True, blank=True, max_length=30, db_index=True, verbose_name="Серийный номер")
    creation_date = models.DateField(null=True, blank=True, verbose_name="Дата производства")
    size = models.IntegerField(choices=BALLOON_SIZE_CHOICES, default=50, verbose_name="Объём")
    netto = models.FloatField(null=True, blank=True, verbose_name="Вес пустого баллона")
    brutto = models.FloatField(null=True, blank=True, verbose_name="Вес наполненного баллона")
    current_examination_date = models.DateField(null=True, blank=True, verbose_name="Дата освидетельствования")
    next_examination_date = models.DateField(null=True, blank=True, verbose_name="Дата следующего освидетельствования")
    diagnostic_date = models.DateField(null=True, blank=True, verbose_name="Дата последней диагностики")
    working_pressure = models.FloatField(null=True, blank=True, verbose_name="Рабочее давление")
    status = models.CharField(null=True, blank=True, max_length=100, verbose_name="Статус")
    manufacturer = models.CharField(null=True, blank=True, max_length=30, verbose_name="Производитель")
    wall_thickness = models.FloatField(null=True, blank=True, verbose_name="Толщина стенок")
    filling_status = models.BooleanField(default=False, verbose_name="Готов к наполнению")
    update_passport_required = models.BooleanField(default=True, verbose_name="Требуется обновление паспорта")
    change_date = models.DateTimeField(auto_now=True, verbose_name="Дата изменений")
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Пользователь",
        default=1
    )

    def __str__(self):
        return self.nfc_tag

    class Meta:
        verbose_name = "Баллон"
        verbose_name_plural = "Баллоны"
        ordering = ['-change_date']

    def get_absolute_url(self):
        return reverse('filling_station:balloon_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('filling_station:balloon_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('filling_station:balloon_delete', args=[self.pk])

    def clean(self):
        if self.brutto and self.netto and self.brutto < self.netto:
            raise ValidationError("Вес наполненного баллона должен быть больше веса пустого баллона.")


class Reader(models.Model):
    number = models.IntegerField(verbose_name="Номер считывателя")
    nfc_tag = models.CharField(max_length=30, verbose_name="Номер метки")
    serial_number = models.CharField(null=True, blank=True, max_length=30, verbose_name="Серийный номер")
    size = models.IntegerField(choices=BALLOON_SIZE_CHOICES, default=50, verbose_name="Объём")
    netto = models.FloatField(null=True, blank=True, verbose_name="Вес пустого баллона")
    brutto = models.FloatField(null=True, blank=True, verbose_name="Вес наполненного баллона")
    filling_status = models.BooleanField(default=False, verbose_name="Готов к наполнению")
    change_date = models.DateField(auto_now=True, verbose_name="Дата изменений")
    change_time = models.TimeField(auto_now=True, verbose_name="Время изменений")

    def __int__(self):
        return self.pk

    def __str__(self):
        return self.number

    class Meta:
        verbose_name = "Считыватель"
        verbose_name_plural = "Считыватели"
        ordering = ['-change_date', '-change_time']


class TruckType(models.Model):
    type = models.CharField(max_length=100, verbose_name="Тип грузовика")

    def __str__(self):
        return self.type

    class Meta:
        verbose_name = "Тип грузовика"
        verbose_name_plural = "Типы грузовиков"


class Truck(models.Model):
    car_brand = models.CharField(null=True, blank=True, max_length=20, verbose_name="Марка авто")
    registration_number = models.CharField(max_length=10, verbose_name="Регистрационный знак")
    type = models.ForeignKey(
        TruckType,
        on_delete=models.DO_NOTHING,
        verbose_name="Тип",
        default=1
    )
    capacity_cylinders = models.IntegerField(null=True, blank=True, verbose_name="Максимальная вместимость баллонов")
    max_weight_of_transported_cylinders = models.FloatField(null=True, blank=True,
                                                            verbose_name="Максимальная масса перевозимых баллонов")
    max_mass_of_transported_gas = models.FloatField(null=True, blank=True,
                                                    verbose_name="Максимальная масса перевозимого газа")
    max_gas_volume = models.FloatField(null=True, blank=True, verbose_name="Максимальный объём перевозимого газа")
    empty_weight = models.FloatField(null=True, blank=True, verbose_name="Вес пустого т/с (по техпаспорту)")
    full_weight = models.FloatField(null=True, blank=True, verbose_name="Вес полного т/с (по техпаспорту)")
    is_on_station = models.BooleanField(null=True, blank=True, verbose_name="Находится на станции")
    entry_date = models.DateField(null=True, blank=True, verbose_name="Дата въезда")
    entry_time = models.TimeField(null=True, blank=True, verbose_name="Время въезда")
    departure_date = models.DateField(null=True, blank=True, verbose_name="Дата выезда")
    departure_time = models.TimeField(null=True, blank=True, verbose_name="Время выезда")

    def __str__(self):
        return self.registration_number

    class Meta:
        verbose_name = "Грузовик"
        verbose_name_plural = "Грузовики"
        ordering = ['-is_on_station', '-entry_date', '-entry_time', '-departure_date', '-departure_time']

    def get_absolute_url(self):
        return reverse('filling_station:truck_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('filling_station:truck_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('filling_station:truck_delete', args=[self.pk])


class TrailerType(models.Model):
    type = models.CharField(max_length=100, verbose_name="Тип прицепа")

    def __str__(self):
        return self.type

    class Meta:
        verbose_name = "Тип прицепа"
        verbose_name_plural = "Типы прицепов"


class Trailer(models.Model):
    truck = models.ForeignKey(
        Truck,
        on_delete=models.DO_NOTHING,
        verbose_name="Автомобиль",
        related_name='trailer',
        default=1
    )
    trailer_brand = models.CharField(null=True, blank=True, max_length=20, verbose_name="Марка прицепа")
    registration_number = models.CharField(max_length=10, verbose_name="Регистрационный знак")
    type = models.ForeignKey(
        TrailerType,
        on_delete=models.DO_NOTHING,
        verbose_name="Тип",
        default=1
    )
    capacity_cylinders = models.IntegerField(null=True, blank=True, verbose_name="Максимальная вместимость баллонов")
    max_weight_of_transported_cylinders = models.FloatField(null=True, blank=True,
                                                            verbose_name="Максимальная масса перевозимых баллонов")
    max_mass_of_transported_gas = models.FloatField(null=True, blank=True,
                                                    verbose_name="Максимальная масса перевозимого газа")
    max_gas_volume = models.FloatField(null=True, blank=True, verbose_name="Максимальный объём перевозимого газа")
    empty_weight = models.FloatField(null=True, blank=True, verbose_name="Вес пустого т/с (по техпаспорту)")
    full_weight = models.FloatField(null=True, blank=True, verbose_name="Вес полного т/с (по техпаспорту)")

    is_on_station = models.BooleanField(null=True, blank=True, verbose_name="Находится на станции")
    entry_date = models.DateField(null=True, blank=True, verbose_name="Дата въезда")
    entry_time = models.TimeField(null=True, blank=True, verbose_name="Время въезда")
    departure_date = models.DateField(null=True, blank=True, verbose_name="Дата выезда")
    departure_time = models.TimeField(null=True, blank=True, verbose_name="Время выезда")

    def __str__(self):
        return self.registration_number

    class Meta:
        verbose_name = "Прицеп"
        verbose_name_plural = "Прицепы"
        ordering = ['-is_on_station', '-entry_date', '-entry_time', '-departure_date', '-departure_time']

    def get_absolute_url(self):
        return reverse('filling_station:trailer_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('filling_station:trailer_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('filling_station:trailer_delete', args=[self.pk])


class BalloonAmount(models.Model):
    reader_id = models.IntegerField(null=True, blank=True, verbose_name="Номер считывателя")
    reader_status = models.CharField(null=True, blank=True, max_length=50, verbose_name="Статус")
    amount_of_balloons = models.IntegerField(null=True, blank=True, verbose_name="Количество баллонов по датчику")
    amount_of_rfid = models.IntegerField(null=True, blank=True, verbose_name="Количество баллонов по считывателю")
    change_date = models.DateField(null=True, blank=True, auto_now=True, verbose_name="Дата обновления")
    change_time = models.TimeField(null=True, blank=True, auto_now=True, verbose_name="Время обновления")


class BalloonsLoadingBatch(models.Model):
    begin_date = models.DateField(auto_now_add=True, verbose_name="Дата начала приёмки")
    begin_time = models.TimeField(auto_now_add=True, verbose_name="Время начала приёмки")
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
    reader_number = models.IntegerField(null=True, blank=True, verbose_name="Номер считывателя")
    amount_of_rfid = models.IntegerField(default=0, verbose_name="Количество баллонов по rfid")
    amount_of_5_liters = models.IntegerField(default=0, verbose_name="Количество 5л баллонов")
    amount_of_12_liters = models.IntegerField(default=0, verbose_name="Количество 12л баллонов")
    amount_of_27_liters = models.IntegerField(default=0, verbose_name="Количество 27л баллонов")
    amount_of_50_liters = models.IntegerField(default=0, verbose_name="Количество 50л баллонов")
    gas_amount = models.FloatField(null=True, blank=True, verbose_name="Количество принятого газа")
    balloon_list = models.ManyToManyField(
        Balloon,
        blank=True,
        verbose_name="Список баллонов"
    )
    is_active = models.BooleanField(default=False, verbose_name="В работе")
    ttn = models.CharField(max_length=20, default='', verbose_name="Номер ТТН")
    amount_of_ttn = models.IntegerField(null=True, blank=True, verbose_name="Количество баллонов по ТТН")
    user = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        default=1,
        verbose_name="Пользователь"
    )

    def __str__(self):
        return str(self.id)

    class Meta:
        verbose_name = "Партия приёмки баллонов"
        verbose_name_plural = "Партии приёмки баллонов"
        ordering = ['-begin_date', '-begin_time']

    def get_absolute_url(self):
        return reverse('filling_station:balloon_loading_batch_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('filling_station:balloon_loading_batch_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('filling_station:balloon_loading_batch_delete', args=[self.pk])

    def get_amount_without_rfid(self):
        amounts = [
            self.amount_of_5_liters or 0,
            self.amount_of_12_liters or 0,
            self.amount_of_27_liters or 0,
            self.amount_of_50_liters or 0
        ]
        total_amount = sum(amounts)
        return total_amount

    @classmethod
    def get_period_stats(cls, start_date=None, end_date=None):
        queryset = cls.objects.filter(begin_date__range=[start_date, end_date])

        return queryset.annotate(
            batch_balloon_count=Count('balloon_list'),
        ).aggregate(
            total_batches=Count('id'),
            total_balloon_count_by_rfid=Sum('batch_balloon_count'),
            total_balloon_count_by_ttn=Sum('amount_of_ttn'),
        )


class BalloonsUnloadingBatch(models.Model):
    begin_date = models.DateField(auto_now_add=True, verbose_name="Дата начала отгрузки")
    begin_time = models.TimeField(auto_now_add=True, verbose_name="Время начала отгрузки")
    end_date = models.DateField(null=True, blank=True, verbose_name="Дата окончания отгрузки")
    end_time = models.TimeField(null=True, blank=True, verbose_name="Время окончания отгрузки")
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
    reader_number = models.IntegerField(null=True, blank=True, verbose_name="Номер считывателя")
    amount_of_rfid = models.IntegerField(default=0, verbose_name="Количество баллонов по rfid")
    amount_of_5_liters = models.IntegerField(default=0, verbose_name="Количество 5л баллонов")
    amount_of_12_liters = models.IntegerField(default=0, verbose_name="Количество 12л баллонов")
    amount_of_27_liters = models.IntegerField(default=0, verbose_name="Количество 27л баллонов")
    amount_of_50_liters = models.IntegerField(default=0, verbose_name="Количество 50л баллонов")
    gas_amount = models.FloatField(null=True, blank=True, verbose_name="Количество отгруженного газа")
    balloon_list = models.ManyToManyField(Balloon, blank=True, verbose_name="Список баллонов")
    is_active = models.BooleanField(default=False, verbose_name="В работе")
    ttn = models.CharField(max_length=20, default='', verbose_name="Номер ТТН")
    amount_of_ttn = models.IntegerField(null=True, blank=True, verbose_name="Количество баллонов по ТТН")
    user = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        default=1,
        verbose_name="Пользователь"
    )

    def __str__(self):
        return str(self.id)

    class Meta:
        verbose_name = "Партия отгрузки баллонов"
        verbose_name_plural = "Партии отгрузки баллонов"
        ordering = ['-begin_date', '-begin_time']

    def get_absolute_url(self):
        return reverse('filling_station:balloon_unloading_batch_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('filling_station:balloon_unloading_batch_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('filling_station:balloon_unloading_batch_delete', args=[self.pk])

    def get_amount_without_rfid(self):
        amounts = [
            self.amount_of_5_liters or 0,
            self.amount_of_12_liters or 0,
            self.amount_of_27_liters or 0,
            self.amount_of_50_liters or 0
        ]
        total_amount = sum(amounts)
        return total_amount

    @classmethod
    def get_period_stats(cls, start_date=None, end_date=None):
        queryset = cls.objects.filter(begin_date__range=[start_date, end_date])

        return queryset.annotate(
            batch_balloon_count=Count('balloon_list'),
        ).aggregate(
            total_batches=Count('id'),
            total_balloon_count_by_rfid=Sum('batch_balloon_count'),
            total_balloon_count_by_ttn=Sum('amount_of_ttn'),
        )
