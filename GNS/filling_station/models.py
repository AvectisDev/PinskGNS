from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.urls import reverse
from django.db.models import Q, Sum
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


BALLOON_SIZE_CHOICES = [
    (5, 5),
    (12, 12),
    (27, 27),
    (50, 50),
]


@pghistory.track(exclude=['filling_status', 'update_passport_required', 'change_date', 'change_time'])
class Balloon(models.Model):
    nfc_tag = models.CharField(null=True, blank=True, max_length=30, verbose_name="Номер метки")
    serial_number = models.CharField(null=True, blank=True, max_length=30, verbose_name="Серийный номер")
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
    change_date = models.DateField(auto_now=True, verbose_name="Дата изменений")
    change_time = models.TimeField(auto_now=True, verbose_name="Время изменений")
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Пользователь",
        default=1
    )

    def __int__(self):
        return f"Balloon {self.nfc_tag}"

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


class Contractor(models.Model):
    name = models.CharField(max_length=200, verbose_name="Контрагент")
    code = models.CharField(max_length=20, null=True, blank=True, verbose_name="Код")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Контрагент"
        verbose_name_plural = "Контрагенты"


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
    begin_date = models.DateField(null=True, blank=True, auto_now_add=True, verbose_name="Дата начала приёмки")
    begin_time = models.TimeField(null=True, blank=True, auto_now_add=True, verbose_name="Время начала приёмки")
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
    amount_of_rfid = models.IntegerField(null=True, blank=True, verbose_name="Количество баллонов по rfid")
    amount_of_5_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 5л баллонов")
    amount_of_12_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 12л баллонов")
    amount_of_27_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 27л баллонов")
    amount_of_50_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 50л баллонов")
    gas_amount = models.FloatField(null=True, blank=True, verbose_name="Количество принятого газа")
    balloon_list = models.ManyToManyField(
        Balloon,
        blank=True,
        verbose_name="Список баллонов"
    )
    is_active = models.BooleanField(null=True, blank=True, verbose_name="В работе")
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


class BalloonsUnloadingBatch(models.Model):
    begin_date = models.DateField(null=True, blank=True, auto_now_add=True, verbose_name="Дата начала отгрузки")
    begin_time = models.TimeField(null=True, blank=True, auto_now_add=True, verbose_name="Время начала отгрузки")
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
    amount_of_rfid = models.IntegerField(null=True, blank=True, verbose_name="Количество баллонов по rfid")
    amount_of_5_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 5л баллонов")
    amount_of_12_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 12л баллонов")
    amount_of_27_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 27л баллонов")
    amount_of_50_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 50л баллонов")
    gas_amount = models.FloatField(null=True, blank=True, verbose_name="Количество отгруженного газа")
    balloon_list = models.ManyToManyField(Balloon, blank=True, verbose_name="Список баллонов")
    is_active = models.BooleanField(null=True, blank=True, verbose_name="В работе")
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


class TTN(models.Model):
    number = models.CharField(blank=False, max_length=100, verbose_name="Номер ТТН")
    contract = models.CharField(blank=True, max_length=100, verbose_name="Номер договора")
    shipper = models.CharField(blank=False, max_length=100, verbose_name="Грузоотправитель")
    carrier = models.CharField(blank=False, max_length=100, verbose_name="Перевозчик")
    consignee = models.CharField(blank=False, max_length=100, verbose_name="Грузополучатель")
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


class NewTTN(models.Model):
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
    loading_batch = models.ForeignKey(
        BalloonsLoadingBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Партия приёмки",
        related_name='ttn_loading'
    )
    unloading_batch = models.ForeignKey(
        BalloonsUnloadingBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Партия отгрузки",
        related_name='ttn_unloading'
    )
    date = models.DateField(null=True, blank=True, verbose_name="Дата формирования накладной")

    def __str__(self):
        return self.number

    class Meta:
        verbose_name = "ТТН на баллоны"
        verbose_name_plural = "ТТН на баллоны"
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
        return reverse('filling_station:ttn_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('filling_station:ttn_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('filling_station:ttn_delete', args=[self.pk])


class RailwayTank(models.Model):
    registration_number = models.CharField(blank=False, max_length=20, verbose_name="Номер ж/д цистерны")
    empty_weight = models.FloatField(null=True, blank=True, verbose_name="Вес пустой цистерны")
    full_weight = models.FloatField(null=True, blank=True, verbose_name="Вес полной цистерны")
    gas_weight = models.FloatField(null=True, blank=True, verbose_name="Масса перевозимого газа")
    gas_type = models.CharField(max_length=10, choices=GAS_TYPE_CHOICES, default='Не выбран', verbose_name="Тип газа")
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
        return reverse('filling_station:railway_tank_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('filling_station:railway_tank_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('filling_station:railway_tank_delete', args=[self.pk])

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
        return reverse('filling_station:railway_batch_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('filling_station:railway_batch_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('filling_station:railway_batch_delete', args=[self.pk])


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
        return reverse('filling_station:railway_ttn_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('filling_station:railway_ttn_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('filling_station:railway_ttn_delete', args=[self.pk])

    def update_gas_amounts(self):
        """Обновляет суммы газа по связанным цистернам"""
        tanks = self.railway_tank_list.all()
        self.total_gas_amount_by_scales = tanks.aggregate(total=Sum('gas_weight'))['total'] or 0
        self.total_gas_amount_by_ttn = tanks.aggregate(total=Sum('netto_weight_ttn'))['total'] or 0
        self.save()


class AutoGasBatch(models.Model):
    batch_type = models.CharField(max_length=10, choices=BATCH_TYPE_CHOICES, default='u', verbose_name="Тип партии")
    begin_date = models.DateField(null=True, blank=True, auto_now_add=True, verbose_name="Дата начала приёмки")
    begin_time = models.TimeField(null=True, blank=True, auto_now_add=True, verbose_name="Время начала приёмки")
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
    gas_type = models.CharField(max_length=10, choices=GAS_TYPE_CHOICES, default='Не выбран', verbose_name="Тип газа")
    scale_empty_weight = models.FloatField(null=True, blank=True, verbose_name="Вес пустого т/с (весы)")
    scale_full_weight = models.FloatField(null=True, blank=True, verbose_name="Вес полного т/с (весы)")
    weight_gas_amount = models.FloatField(null=True, blank=True, verbose_name="Количество газа (весы)")
    is_active = models.BooleanField(null=True, blank=True, verbose_name="В работе")
    ttn = models.ForeignKey(
        TTN,
        on_delete=models.DO_NOTHING,
        default=0,
        verbose_name="ТТН"
    )
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

    def get_absolute_url(self):
        return reverse('filling_station:auto_gas_batch_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('filling_station:auto_gas_batch_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('filling_station:auto_gas_batch_delete', args=[self.pk])


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
        verbose_name = "ТТН на автоцистерны"
        verbose_name_plural = "ТТН на автоцистерны"
        ordering = ['-id', '-date']

    def get_absolute_url(self):
        return reverse('filling_station:auto_ttn_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('filling_station:auto_ttn_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('filling_station:auto_ttn_delete', args=[self.pk])


class FilePath(models.Model):
    path = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.path or "API"

