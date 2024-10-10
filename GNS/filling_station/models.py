from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
import pghistory

GAS_TYPE_CHOICES = [
    ('Не выбран', 'Не выбран'),
    ('СПБТ', 'СПБТ'),
    ('ПБА', 'ПБА'),
]

BATCH_TYPE_CHOICES = [
    ('l', 'Приёмка'),
    ('u', 'Отгрузка'),
]


@pghistory.track(exclude=['filling_status', 'update_passport_required', 'change_date', 'change_time'])
class Balloon(models.Model):
    nfc_tag = models.CharField(max_length=30, verbose_name="Номер метки")
    serial_number = models.CharField(null=True, blank=True, max_length=30, verbose_name="Серийный номер")
    creation_date = models.DateField(null=True, blank=True, verbose_name="Дата производства")
    size = models.FloatField(null=True, blank=True, verbose_name="Объём")
    netto = models.FloatField(null=True, blank=True, verbose_name="Вес пустого баллона")
    brutto = models.FloatField(null=True, blank=True, verbose_name="Вес наполненного баллона")
    current_examination_date = models.DateField(null=True, blank=True, verbose_name="Дата освидетельствования")
    next_examination_date = models.DateField(null=True, blank=True, verbose_name="Дата следующего освидетельствования")
    status = models.CharField(null=True, blank=True, max_length=100, verbose_name="Статус")
    manufacturer = models.CharField(null=True, blank=True, max_length=30, verbose_name="Производитель")
    wall_thickness = models.FloatField(null=True, blank=True, verbose_name="Толщина стенок")
    filling_status = models.BooleanField(null=True, blank=True, verbose_name="Готов к наполнению")
    update_passport_required = models.BooleanField(null=True, blank=True, verbose_name="Требуется обновление паспорта")
    change_date = models.DateField(null=True, blank=True, auto_now=True, verbose_name="Дата изменений")
    change_time = models.TimeField(null=True, blank=True, auto_now=True, verbose_name="Время изменений")
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, verbose_name="Пользователь", default=1)

    def __str__(self):
        return self.nfc_tag

    class Meta:
        verbose_name = "Баллон"
        verbose_name_plural = "Баллоны"
        ordering = ['-change_date', '-change_time']
        indexes = [
            models.Index(fields=['-nfc_tag', '-serial_number']),
        ]

    def get_absolute_url(self):
        return reverse('filling_station:balloon_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('filling_station:balloon_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('filling_station:balloon_delete', args=[self.pk])


class Truck(models.Model):
    car_brand = models.CharField(null=True, blank=True, max_length=20, verbose_name="Марка авто")
    registration_number = models.CharField(max_length=10, verbose_name="Регистрационный знак")
    type = models.CharField(null=True, blank=True, max_length=50, verbose_name="Тип")
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
        ordering = ['-entry_date', '-entry_time']

    def get_absolute_url(self):
        return reverse('filling_station:truck_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('filling_station:truck_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('filling_station:truck_delete', args=[self.pk])


class Trailer(models.Model):
    truck = models.ForeignKey(Truck, on_delete=models.DO_NOTHING, verbose_name="Автомобиль", related_name='trailer',
                              default=1)
    trailer_brand = models.CharField(null=True, blank=True, max_length=20, verbose_name="Марка прицепа")
    registration_number = models.CharField(max_length=10, verbose_name="Регистрационный знак")
    type = models.CharField(null=True, blank=True, max_length=50, verbose_name="Тип")
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
        ordering = ['-entry_date', '-entry_time']

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


class TTN(models.Model):
    number = models.CharField(blank=False, max_length=20, verbose_name="Номер ТТН")
    contract = models.CharField(blank=False, max_length=20, verbose_name="Номер договора")
    shipper = models.CharField(blank=False, max_length=20, verbose_name="Грузоотправитель")
    consignee = models.CharField(blank=False, max_length=20, verbose_name="Грузополучатель")
    gas_amount = models.FloatField(null=True, blank=True, verbose_name="Количество газа")
    gas_type = models.CharField(max_length=10, choices=GAS_TYPE_CHOICES, default='Не выбран', verbose_name="Тип газа")
    balloons_amount = models.IntegerField(null=True, blank=True, verbose_name="Количество баллонов")
    date = models.DateField(null=True, blank=True, verbose_name="Дата формирования накладной")

    def __str__(self):
        return self.number

    class Meta:
        verbose_name = "ТТН"
        verbose_name_plural = "ТТН"
        ordering = ['-date']

    def get_absolute_url(self):
        return reverse('filling_station:ttn_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('filling_station:ttn_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('filling_station:ttn_delete', args=[self.pk])


class BalloonsLoadingBatch(models.Model):
    begin_date = models.DateField(null=True, blank=True, auto_now_add=True, verbose_name="Дата начала приёмки")
    begin_time = models.TimeField(null=True, blank=True, auto_now_add=True, verbose_name="Время начала приёмки")
    end_date = models.DateField(null=True, blank=True, verbose_name="Дата окончания приёмки")
    end_time = models.TimeField(null=True, blank=True, verbose_name="Время окончания приёмки")
    truck = models.ForeignKey(Truck, on_delete=models.DO_NOTHING, verbose_name="Автомобиль")
    trailer = models.ForeignKey(Trailer, on_delete=models.DO_NOTHING, null=True, blank=True, default=0,
                                verbose_name="Прицеп")
    reader_number = models.IntegerField(null=True, blank=True, verbose_name="Номер считывателя")
    amount_of_rfid = models.IntegerField(null=True, blank=True, verbose_name="Количество баллонов по rfid")
    amount_of_5_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 5л баллонов")
    amount_of_12_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 12л баллонов")
    amount_of_27_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 27л баллонов")
    amount_of_50_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 50л баллонов")
    gas_amount = models.FloatField(null=True, blank=True, verbose_name="Количество принятого газа")
    balloon_list = models.ManyToManyField(Balloon, blank=True, verbose_name="Список баллонов")
    is_active = models.BooleanField(null=True, blank=True, verbose_name="В работе")
    ttn = models.ForeignKey(TTN, on_delete=models.DO_NOTHING, default=0, verbose_name="ТТН")
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, default=1, verbose_name="Пользователь")

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


class BalloonsUnloadingBatch(models.Model):
    begin_date = models.DateField(null=True, blank=True, auto_now_add=True, verbose_name="Дата начала отгрузки")
    begin_time = models.TimeField(null=True, blank=True, auto_now_add=True, verbose_name="Время начала отгрузки")
    end_date = models.DateField(null=True, blank=True, verbose_name="Дата окончания отгрузки")
    end_time = models.TimeField(null=True, blank=True, verbose_name="Время окончания отгрузки")
    truck = models.ForeignKey(Truck, on_delete=models.DO_NOTHING, verbose_name="Автомобиль")
    trailer = models.ForeignKey(Trailer, on_delete=models.DO_NOTHING, null=True, blank=True, default=0,
                                verbose_name="Прицеп")
    reader_number = models.IntegerField(null=True, blank=True, verbose_name="Номер считывателя")
    amount_of_rfid = models.IntegerField(null=True, blank=True, verbose_name="Количество баллонов по rfid")
    amount_of_5_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 5л баллонов")
    amount_of_12_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 12л баллонов")
    amount_of_27_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 27л баллонов")
    amount_of_50_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 50л баллонов")
    gas_amount = models.FloatField(null=True, blank=True, verbose_name="Количество отгруженного газа")
    balloon_list = models.ManyToManyField(Balloon, blank=True, verbose_name="Список баллонов")
    is_active = models.BooleanField(null=True, blank=True, verbose_name="В работе")
    ttn = models.ForeignKey(TTN, on_delete=models.DO_NOTHING, default=0, verbose_name="ТТН")
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, default=1, verbose_name="Пользователь")

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


class RailwayTank(models.Model):
    registration_number = models.CharField(blank=False, max_length=10, verbose_name="Номер ж/д цистерны")
    empty_weight = models.FloatField(null=True, blank=True, verbose_name="Вес пустой цистерны")
    full_weight = models.FloatField(null=True, blank=True, verbose_name="Вес полной цистерны")
    gas_weight = models.FloatField(null=True, blank=True, verbose_name="Масса перевозимого газа")
    gas_type = models.CharField(max_length=10, choices=GAS_TYPE_CHOICES, default='Не выбран', verbose_name="Тип газа")
    is_on_station = models.BooleanField(null=True, blank=True, verbose_name="Находится на станции")
    entry_date = models.DateField(null=True, blank=True, verbose_name="Дата въезда")
    entry_time = models.TimeField(null=True, blank=True, verbose_name="Время въезда")
    departure_date = models.DateField(null=True, blank=True, verbose_name="Дата выезда")
    departure_time = models.TimeField(null=True, blank=True, verbose_name="Время выезда")

    def __str__(self):
        return self.registration_number

    class Meta:
        verbose_name = "Ж/д цистерна"
        verbose_name_plural = "Ж/д цистерны"
        ordering = ['-entry_date', '-entry_time']

    def get_absolute_url(self):
        return reverse('filling_station:railway_tank_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('filling_station:railway_tank_update', args=[self.pk])


class RailwayBatch(models.Model):
    begin_date = models.DateField(null=True, blank=True, auto_now_add=True, verbose_name="Дата начала приёмки")
    begin_time = models.TimeField(null=True, blank=True, auto_now_add=True, verbose_name="Время начала приёмки")
    end_date = models.DateField(null=True, blank=True, verbose_name="Дата окончания приёмки")
    end_time = models.TimeField(null=True, blank=True, verbose_name="Время окончания приёмки")
    gas_amount_spbt = models.FloatField(null=True, blank=True, verbose_name="Количество принятого СПБТ газа")
    gas_amount_pba = models.FloatField(null=True, blank=True, verbose_name="Количество принятого ПБА газа")
    railway_tank_list = models.ManyToManyField(RailwayTank, blank=True, verbose_name="Список жд цистерн")
    is_active = models.BooleanField(null=True, blank=True, verbose_name="В работе")
    ttn = models.ForeignKey(TTN, on_delete=models.DO_NOTHING, default=0, verbose_name="ТТН")
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, default=0, verbose_name="Пользователь")

    class Meta:
        verbose_name = "Партия приёмки жд цистерн"
        verbose_name_plural = "Партии приёмки жд цистерн"
        ordering = ['-begin_date', '-begin_time']

    def get_absolute_url(self):
        return reverse('filling_station:railway_batch_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('filling_station:railway_batch_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('filling_station:railway_batch_delete', args=[self.pk])


class AutoGasBatch(models.Model):
    batch_type = models.CharField(max_length=10, choices=BATCH_TYPE_CHOICES, default='u', verbose_name="Тип партии")
    begin_date = models.DateField(null=True, blank=True, auto_now_add=True, verbose_name="Дата начала приёмки")
    begin_time = models.TimeField(null=True, blank=True, auto_now_add=True, verbose_name="Время начала приёмки")
    end_date = models.DateField(null=True, blank=True, verbose_name="Дата окончания приёмки")
    end_time = models.TimeField(null=True, blank=True, verbose_name="Время окончания приёмки")
    truck = models.ForeignKey(Truck, on_delete=models.DO_NOTHING, verbose_name="Автомобиль")
    trailer = models.ForeignKey(Trailer, on_delete=models.DO_NOTHING, null=True, blank=True, default=0,
                                verbose_name="Прицеп")
    gas_amount = models.FloatField(null=True, blank=True, verbose_name="Количество газа (массомер)")
    gas_type = models.CharField(max_length=10, choices=GAS_TYPE_CHOICES, default='Не выбран', verbose_name="Тип газа")
    scale_empty_weight = models.FloatField(null=True, blank=True, verbose_name="Вес пустого т/с (весы)")
    scale_full_weight = models.FloatField(null=True, blank=True, verbose_name="Вес полного т/с (весы)")
    weight_gas_amount = models.FloatField(null=True, blank=True, verbose_name="Количество газа (весы)")
    is_active = models.BooleanField(null=True, blank=True, verbose_name="В работе")
    ttn = models.ForeignKey(TTN, on_delete=models.DO_NOTHING, default=0, verbose_name="ТТН")
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, default=1, verbose_name="Пользователь")

    class Meta:
        verbose_name = "Автоколонка"
        verbose_name_plural = "Автоколонка"
        ordering = ['-begin_date', '-begin_time']

    def get_absolute_url(self):
        return reverse('filling_station:auto_gas_batch_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('filling_station:auto_gas_batch_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('filling_station:auto_gas_batch_delete', args=[self.pk])
