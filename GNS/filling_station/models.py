from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField


class Balloon(models.Model):
    STATE = {"r": "Зарегистрирован", "f": "Наполнение", "e": "На рампе", "o": "Отгружен"}

    nfc_tag = models.CharField(blank=False, max_length=30, verbose_name="Номер метки")
    serial_number = models.CharField(null=True, blank=True, max_length=30, verbose_name="Серийный номер")
    creation_date = models.DateField(null=True, blank=True, verbose_name="Дата производства")
    size = models.FloatField(null=True, blank=True, verbose_name="Объём")
    netto = models.FloatField(null=True, blank=True, verbose_name="Вес пустого баллона")
    brutto = models.FloatField(null=True, blank=True, verbose_name="Вес наполненного баллона")
    current_examination_date = models.DateField(null=True, blank=True, verbose_name="Дата освидетельствования")
    next_examination_date = models.DateField(null=True, blank=True, verbose_name="Дата следующего освидетельствования")
    manufacturer = models.CharField(null=True, blank=True, max_length=30, verbose_name="Производитель")
    wall_thickness = models.FloatField(null=True, blank=True, verbose_name="Толщина стенок")
    status = models.CharField(blank=True, max_length=100, verbose_name="Статус")
    filling_status = models.IntegerField(null=True, blank=True, verbose_name="Готов к наполнению")
    update_passport_required = models.BooleanField(null=True, blank=True, verbose_name="Требуется обновление паспорта")
    change_date = models.DateField(null=True, blank=True, auto_now_add=True, verbose_name="Дата изменений")
    change_time = models.TimeField(null=True, blank=True, auto_now_add=True, verbose_name="Время изменений")
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, verbose_name="Пользователь")

    def __str__(self):
        return self.nfc_tag

    class Meta:
        verbose_name = "Баллон"
        verbose_name_plural = "Баллоны"


class Truck(models.Model):
    car_brand = models.CharField(null=True, blank=False, max_length=20, verbose_name="Марка авто")
    registration_number = models.CharField(blank=False, max_length=10, verbose_name="Регистрационный знак")
    type = models.CharField(blank=False, max_length=50, verbose_name="Тип")
    max_capacity_cylinders_by_type = models.IntegerField(null=True, blank=True,
                                                         verbose_name="Максимальная вместимость баллонов")
    max_weight_of_transported_cylinders = models.IntegerField(null=True, blank=True,
                                                              verbose_name="Максимальная масса перевозимых баллонов")
    max_mass_of_transported_gas = models.IntegerField(null=True, blank=True,
                                                      verbose_name="Максимальная масса перевозимого газа")
    empty_weight = models.IntegerField(null=True, blank=True, verbose_name="Вес пустого т/с")
    full_weight = models.IntegerField(null=True, blank=True, verbose_name="Вес полного т/с")
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


class Trailer(models.Model):
    trailer_brand = models.CharField(null=True, blank=False, max_length=20, verbose_name="Марка прицепа")
    registration_number = models.CharField(blank=False, max_length=10, verbose_name="Регистрационный знак")
    type = models.CharField(blank=False, max_length=50, verbose_name="Тип")
    max_capacity_cylinders_by_type = models.IntegerField(null=True, blank=True,
                                                         verbose_name="Максимальная вместимость баллонов")
    max_weight_of_transported_cylinders = models.IntegerField(null=True, blank=True,
                                                              verbose_name="Максимальная масса перевозимых баллонов")
    max_mass_of_transported_gas = models.IntegerField(null=True, blank=True,
                                                      verbose_name="Максимальная масса перевозимого газа")
    empty_weight = models.IntegerField(null=True, blank=True, verbose_name="Вес пустого т/с")
    full_weight = models.IntegerField(null=True, blank=True, verbose_name="Вес полного т/с")
    is_on_station = models.BooleanField(null=True, blank=True, verbose_name="Находится на станции")

    def __str__(self):
        return self.registration_number

    class Meta:
        verbose_name = "Прицеп"
        verbose_name_plural = "Прицепы"


class RailwayTanks(models.Model):
    number = models.CharField(blank=False, max_length=10, verbose_name="Номер ж/д цистерны")
    empty_weight = models.IntegerField(null=True, blank=True, verbose_name="Вес пустой цистерны")
    full_weight = models.IntegerField(null=True, blank=True, verbose_name="Вес полной цистерны")
    is_on_station = models.BooleanField(null=True, blank=True, verbose_name="Находится на станции")
    entry_date = models.DateField(null=True, blank=True, verbose_name="Дата въезда")
    entry_time = models.TimeField(null=True, blank=True, verbose_name="Время въезда")
    departure_date = models.DateField(null=True, blank=True, verbose_name="Дата выезда")
    departure_time = models.TimeField(null=True, blank=True, verbose_name="Время выезда")

    def __str__(self):
        return self.number

    class Meta:
        verbose_name = "Ж/д цистерна"
        verbose_name_plural = "Ж/д цистерны"


class BalloonAmount(models.Model):
    reader_id = models.IntegerField(null=True, blank=True, verbose_name="Номер считывателя")
    amount_of_balloons = models.IntegerField(null=True, blank=True, verbose_name="Количество баллонов по датчику")
    change_date = models.DateField(null=True, blank=True, auto_now_add=True, verbose_name="Дата обновления")
    change_time = models.TimeField(null=True, blank=True, auto_now_add=True, verbose_name="Время обновления")


class TTN(models.Model):
    number = models.CharField(blank=False, max_length=20, verbose_name="Номер ТТН")
    contract = models.CharField(blank=False, max_length=20, verbose_name="Номер договора")
    name_of_supplier = models.CharField(blank=False, max_length=20, verbose_name="Поставщик")
    gas_amount = models.FloatField(null=True, blank=True, verbose_name="Количество газа")
    balloons_amount = models.FloatField(null=True, blank=True, verbose_name="Количество баллонов")
    date = models.DateField(null=True, blank=True, verbose_name="Дата формирования накладной")

    def __str__(self):
        return self.number

    class Meta:
        verbose_name = "Баллон"
        verbose_name_plural = "Баллоны"


class ShippingBatchBalloons(models.Model):
    begin_date = models.DateField(null=True, blank=True, verbose_name="Дата начала приёмки")
    begin_time = models.TimeField(null=True, blank=True, verbose_name="Время начала приёмки")
    end_date = models.DateField(null=True, blank=True, verbose_name="Дата окончания приёмки")
    end_time = models.TimeField(null=True, blank=True, verbose_name="Время окончания приёмки")
    truck = models.ForeignKey(Truck, on_delete=models.DO_NOTHING, verbose_name="Автомобиль")
    trailer = models.ForeignKey(Trailer, on_delete=models.DO_NOTHING, null=True, blank=True, default=0, verbose_name="Прицеп")
    amount_of_rfid = models.IntegerField(null=True, blank=True, verbose_name="Количество баллонов по rfid")
    amount_of_5_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 5л баллонов")
    amount_of_20_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 20л баллонов")
    amount_of_50_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 50л баллонов")
    gas_amount = models.FloatField(null=True, blank=True, verbose_name="Количество принятого газа")
    balloons_list = ArrayField(models.CharField(max_length=20), blank=True)
    is_active = models.BooleanField(null=True, blank=True, verbose_name="В работе")
    ttn = models.ForeignKey(TTN, on_delete=models.DO_NOTHING, default=0, verbose_name="ТТН")
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, default=0, verbose_name="Пользователь")

    # def __str__(self):
    #     return self.id

    class Meta:
        verbose_name = "Партия приёмки баллонов"
        verbose_name_plural = "Партии приёмки баллонов"


class ReceivingBatchBalloons(models.Model):
    begin_date = models.DateField(null=True, blank=True, verbose_name="Дата начала отгрузки")
    begin_time = models.TimeField(null=True, blank=True, verbose_name="Время начала отгрузки")
    end_date = models.DateField(null=True, blank=True, verbose_name="Дата окончания отгрузки")
    end_time = models.TimeField(null=True, blank=True, verbose_name="Время окончания отгрузки")
    truck = models.ForeignKey(Truck, on_delete=models.DO_NOTHING, verbose_name="Автомобиль")
    trailer = models.ForeignKey(Trailer, on_delete=models.DO_NOTHING, null=True, blank=True, default=0, verbose_name="Прицеп")
    amount_of_rfid = models.IntegerField(null=True, blank=True, verbose_name="Количество баллонов по rfid")
    amount_of_5_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 5л баллонов")
    amount_of_20_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 20л баллонов")
    amount_of_50_liters = models.IntegerField(null=True, blank=True, default=0, verbose_name="Количество 50л баллонов")
    gas_amount = models.FloatField(null=True, blank=True, verbose_name="Количество отгруженного газа")
    balloons_list = ArrayField(models.CharField(max_length=20), blank=True)
    is_active = models.BooleanField(null=True, blank=True, verbose_name="В работе")
    ttn = models.ForeignKey(TTN, on_delete=models.DO_NOTHING, default=0, verbose_name="ТТН")
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, default=0, verbose_name="Пользователь")

    # def __str__(self):
    #     return self.id

    class Meta:
        verbose_name = "Партия отгрузки баллонов"
        verbose_name_plural = "Партии отгрузки баллонов"


class ShippingBatchRailway(models.Model):
    begin_date = models.DateField(null=True, blank=True, verbose_name="Дата начала приёмки")
    begin_time = models.TimeField(null=True, blank=True, verbose_name="Время начала приёмки")
    end_date = models.DateField(null=True, blank=True, verbose_name="Дата окончания приёмки")
    end_time = models.TimeField(null=True, blank=True, verbose_name="Время окончания приёмки")
    gas_amount = models.FloatField(null=True, blank=True, verbose_name="Количество принятого газа")
    railway_tanks_list = ArrayField(models.CharField(max_length=20), blank=True, verbose_name="Список жд цистерн")
    is_active = models.BooleanField(null=True, blank=True, verbose_name="В работе")
    ttn = models.ForeignKey(TTN, on_delete=models.DO_NOTHING, default=0, verbose_name="ТТН")
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, default=0, verbose_name="Пользователь")

    # def __str__(self):
    #     return self.id

    class Meta:
        verbose_name = "Партия приёмки жд цистерн"
        verbose_name_plural = "Партии приёмки жд цистерн"
