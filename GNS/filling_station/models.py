from collections import defaultdict
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.urls import reverse
from django.db.models import Q, Sum, Count
from django.conf import settings
from typing import Dict, Any, Optional
from datetime import datetime, date, time
import pghistory


@pghistory.track(exclude=['filling_status', 'update_passport_required'])
class Balloon(models.Model):
    """
    Модель для хранения информации о газовых баллонах.
    Отслеживает историю изменений через django-pghistory (исключая filling_status и update_passport_required).
    Содержит полные технические характеристики и текущий статус баллона.
    """
    nfc_tag = models.CharField(primary_key=True,max_length=30, db_index=True, verbose_name="Номер метки")
    serial_number = models.CharField(null=True, blank=True, max_length=30, db_index=True, verbose_name="Серийный номер")
    creation_date = models.DateField(null=True, blank=True, verbose_name="Дата производства")
    size = models.IntegerField(choices=settings.BALLOON_SIZE_CHOICES, default=50, verbose_name="Объём")
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

    @classmethod
    def get_balloons_stats(cls):
        """
        Получение статистики полных и пустых баллонов на станции
        """
        stat = {
            # Полных баллонов на станции
            'filled': cls.objects.filter(
                status='Регистрация полного баллона на складе'
                ).count(),
            # Пустых
            'empty': (cls.objects.filter(
                status__in=['Регистрация пустого баллона на складе (рампа)',
                            'Регистрация пустого баллона на складе (цех)']
                ).count())
        }
        return stat


READER_FUNCTION_CHOICES = [
    ('l', 'Приёмка'),
    ('u', 'Отгрузка'),
    ('p', 'Нет')
]

class ReaderSettings(models.Model):
    """
    Модель для хранения конфигурации RFID-считывателей.
    Содержит сетевые настройки и функциональное назначение каждого считывателя.
    Используется для управления взаимодействием с физическими устройствами.
    """
    number = models.IntegerField(primary_key=True, verbose_name="Номер считывателя")
    status = models.CharField(null=True, blank=True, max_length=100, verbose_name="Статус")
    ip = models.CharField(null=True, max_length=15, verbose_name="IP адрес")
    port = models.IntegerField(default=10001, verbose_name="Порт")
    function = models.CharField(choices=READER_FUNCTION_CHOICES, default='p', verbose_name="Функция")
    need_cache = models.BooleanField(default=False, verbose_name="Добавлять в кеш")

    def __int__(self):
        return self.number

    def __str__(self):
        return self.status

    class Meta:
        verbose_name = "Настройки считывателей"
        verbose_name_plural = "Настройки считывателей"
        ordering = ['number']


class Reader(models.Model):
    """
    Модель для хранения данных о считанных RFID-метках баллонов.
    """
    number = models.ForeignKey(
        ReaderSettings,
        on_delete=models.PROTECT,
        verbose_name="Номер считывателя",
        related_name='reader_settings'
    )
    nfc_tag = models.CharField(null=True, blank=True, max_length=30, verbose_name="Номер метки")
    serial_number = models.CharField(null=True, blank=True, max_length=30, verbose_name="Серийный номер")
    size = models.IntegerField(choices=settings.BALLOON_SIZE_CHOICES, default=50, verbose_name="Объём")
    netto = models.FloatField(null=True, blank=True, verbose_name="Вес пустого баллона")
    brutto = models.FloatField(null=True, blank=True, verbose_name="Вес наполненного баллона")
    filling_status = models.BooleanField(default=False, verbose_name="Готов к наполнению")
    change_date = models.DateTimeField(auto_now=True, verbose_name="Дата изменений")

    def __int__(self):
        return self.pk

    def __str__(self):
        return str(self.number)

    class Meta:
        verbose_name = "Считыватель"
        verbose_name_plural = "Считыватели"
        ordering = ['-change_date']

    @classmethod
    def get_reader_stats(cls, reader_number: int, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Получает статистику по считывателю за указанный период.
    
        Собирает:
        - Количество баллонов с RFID-метками (total_rfid)
        - Общее количество баллонов (total_balloons)
        - Список всех баллонов (balloons_list)
        - Для специализированных считывателей (3,4,6) - количество баллонов по ТТН

        Args:
            reader_number: Номер считывателя
            start_date: Начальная дата периода
            end_date: Конечная дата периода

        Returns:
            Словарь с статистикой:
            {
                'total_rfid': int,
                'total_balloons': int,
                'balloons_list': QuerySet['Reader'],
                'loading_ttn_quantity': Optional[int],  # Только для reader_number=6
                'unloading_ttn_quantity': Optional[int]  # Только для reader_number=3,4
            }
        """
        start_datetime = datetime.combine(start_date, time.min)
        end_datetime = datetime.combine(end_date, time.max)

        queryset = cls.objects.filter(
            number=reader_number,
            change_date__range=(start_datetime, end_datetime)
        )

        # Общее количество баллонов с меткой и без, пройдённое через считыватель
        stats = queryset.aggregate(
            total_rfid=Count('pk', filter=Q(nfc_tag__isnull=False)),
            total_balloons=Count('pk')
        )

        # Список баллонов для отображения в шаблоне
        stats['balloons_list'] = queryset.filter(nfc_tag__isnull=False)

        # Статистика по ТТН
        if reader_number == 6:
            stats['loading_ttn_quantity'] = BalloonsLoadingBatch.objects.filter(
                reader_number=reader_number,
                begin_date__range=(start_date, end_date)
            ).aggregate(total_ttn=Sum('amount_of_ttn'))['total_ttn'] or 0
        elif reader_number in [3, 4]:
            stats['unloading_ttn_quantity'] = BalloonsUnloadingBatch.objects.filter(
                reader_number=reader_number,
                begin_date__range=(start_date, end_date)
            ).aggregate(total_ttn=Sum('amount_of_ttn'))['total_ttn'] or 0

        return stats

    @classmethod
    def get_all_readers_stats(cls, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Получает статистику по всем считывателям за указанный период.
        Для каждого считывателя возвращает:
        - Номер считывателя (number)
        - Статус считывателя (status)
        - Количество баллонов с RFID-метками (total_rfid)
        - Общее количество баллонов (total_balloons)

        Args:
            start_date (date): Начальная дата периода
            end_date (date): Конечная дата периода

        Returns:
        QuerySet: Результат в виде queryset словарей со следующими ключами:
        {
            'number': int,             # Номер считывателя
            'status': str,             # Статус считывателя
            'total_rfid': int,         # Количество баллонов с RFID
            'total_balloons': int      # Общее количество баллонов
        }
        """
        start_datetime = datetime.combine(start_date, time.min)
        end_datetime = datetime.combine(end_date, time.max)

        # Получаем общее количество баллонов для каждого ридера за период
        result = ReaderSettings.objects.annotate(
            total_rfid=Count('number', filter=Q(
                reader_settings__change_date__range=[start_datetime, end_datetime],
                reader_settings__nfc_tag__isnull=False
            )),
            total_balloons=Count('number', filter=Q(
                reader_settings__change_date__range=[start_datetime, end_datetime]
            )),
        ).values('number', 'total_rfid', 'total_balloons', 'status').order_by('number')

        return result

    @classmethod
    def get_common_stats_for_gns(cls) -> list:
        today = date.today()
        first_day_of_month = today.replace(day=1)

        month_start = datetime.combine(first_day_of_month, time.min)
        today_start = datetime.combine(today, time.min)

        # Получаем все записи за месяц и день
        month_queryset = cls.objects.filter(change_date__gte=month_start)
        today_queryset = cls.objects.filter(change_date__gte=today_start)

        month_stats = month_queryset.values('number').annotate(
            balloons_month=Count('pk'),
            rfid_month=Count('pk', filter=Q(nfc_tag__isnull=False))
        )

        today_stats = today_queryset.values('number').annotate(
            balloons_today=Count('pk'),
            rfid_today=Count('pk', filter=Q(nfc_tag__isnull=False))
        )

        # Преобразуем в словари для быстрого доступа
        month_dict = {stat['number']: stat for stat in month_stats}
        today_dict = {stat['number']: stat for stat in today_stats}

        stats = []
        for reader in ReaderSettings.objects.all():
            reader_id = reader.number
            month = month_dict.get(reader_id, {})
            today = today_dict.get(reader_id, {})

            stats.append({
                "reader_id": reader_id,
                "balloons_month": month.get('balloons_month', 0),
                "rfid_month": month.get('rfid_month', 0),
                "balloons_today": today.get('balloons_today', 0),
                "rfid_today": today.get('rfid_today', 0),
            })

        return stats


class TruckType(models.Model):
    """Справочник типов грузового транспорта (Клетевоз, Трал и др.)"""
    type = models.CharField(max_length=100, verbose_name="Тип грузовика")

    def __str__(self):
        return self.type

    class Meta:
        verbose_name = "Тип грузовика"
        verbose_name_plural = "Типы грузовиков"


class Truck(models.Model):
    """
    Модель грузового автомобиля для перевозки газовых баллонов.
    Содержит:
    - Регистрационные данные (марка, номер)
    - Технические характеристики (грузоподъемность, объем)
    - Текущий статус (на станции/в рейсе)
    - Временные метки въезда/выезда
    """
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
    is_on_station = models.BooleanField(default=False, verbose_name="Находится на станции")
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
    """Справочник типов прицепов (Прицеп бортовой, Полуприцеп и др.)"""
    type = models.CharField(max_length=100, verbose_name="Тип прицепа")

    def __str__(self):
        return self.type

    class Meta:
        verbose_name = "Тип прицепа"
        verbose_name_plural = "Типы прицепов"


class Trailer(models.Model):
    """
    Модель прицепа для перевозки газовых баллонов.
    Содержит:
    - Регистрационные данные (марка, номер)
    - Технические характеристики (грузоподъемность, объем)
    - Текущий статус (на станции/в рейсе)
    - Временные метки въезда/выезда
    """
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

    is_on_station = models.BooleanField(default=False, verbose_name="Находится на станции")
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


class BalloonsLoadingBatch(models.Model):
    """
    Партия баллонов для погрузки в транспорт.
    Содержит:
    - Временные метки начала/окончания погрузки
    - Данные транспорта (грузовик и прицеп)
    - Статистику по количеству баллонов (по объёмам и RFID)
    - Список загруженных баллонов (ManyToMany)
    - Номер и количество по ТТН
    - Статус активности партии
    """
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

    def get_amount_without_rfid(self) -> int:
        """
        Возвращает общее количество баллонов без меток
        """
        amounts = [
            self.amount_of_5_liters or 0,
            self.amount_of_12_liters or 0,
            self.amount_of_27_liters or 0,
            self.amount_of_50_liters or 0
        ]
        total_amount = sum(amounts)
        return total_amount

    def add_balloon(self, nfc_tag) -> dict:
        """
        Добавляет баллон в партию по NFC-метке
        Возвращает словарь с результатами операции:
        {
            'success': bool,
            'balloon_id': int | None,
            'new_count': int,
            'error': str
        }
        """
        result = {
            'success': False,
            'balloon_id': None,
            'new_count': self.amount_of_rfid or 0,
            'error': 'ok'
        }

        try:
            if self.balloon_list.filter(nfc_tag=nfc_tag).exists():
                result['error'] = 'Баллон уже в партии'
                return result

            balloon = Balloon.objects.get(nfc_tag=nfc_tag)
            self.balloon_list.add(balloon)
            self.amount_of_rfid = (self.amount_of_rfid or 0) + 1
            self.save()

            result.update({
                'success': True,
                'balloon_id': balloon.nfc_tag,
                'new_count': self.amount_of_rfid
            })

        except Balloon.DoesNotExist:
            result['error'] = 'Баллон не найден'
        except Exception as e:
            result['error'] = f'Ошибка сервера: {str(e)}'

        return result

    def remove_balloon(self, nfc_tag) -> dict:
        """
        Удаляет баллон из партии по NFC-метке
        Возвращает словарь с результатами операции:
        {
            'success': bool,
            'balloon_id': int | None,
            'new_count': int,
            'error': str
        }
        """
        result = {
            'success': False,
            'balloon_id': None,
            'new_count': self.amount_of_rfid or 0,
            'error': 'ok'
        }

        try:
            if not self.balloon_list.filter(nfc_tag=nfc_tag).exists():
                result['error'] = 'Баллон не найден в партии'
                return result

            balloon = Balloon.objects.get(nfc_tag=nfc_tag)
            self.balloon_list.remove(balloon)
            self.amount_of_rfid = max((self.amount_of_rfid or 0) - 1, 0)
            self.save()

            result.update({
                'success': True,
                'balloon_id': balloon.nfc_tag,
                'new_count': self.amount_of_rfid
            })

        except Balloon.DoesNotExist:
            result['error'] = 'Баллон не найден'
        except Exception as e:
            result['error'] = f'Ошибка сервера: {str(e)}'

        return result

    @classmethod
    def get_period_stats(cls, start_date: Optional[date]=None, end_date: Optional[date]=None) -> Dict[str, Optional[int]]:
        """
        Собирает статистику по партиям за период:
        - кол-во партий
        - кол-во баллонов с RFID
        - кол-во баллонов по ТТН
        """
        queryset = cls.objects.filter(begin_date__range=[start_date, end_date])

        return queryset.annotate(
            batch_balloon_count=Count('balloon_list'),
        ).aggregate(
            total_batches=Count('id'),
            total_balloon_count_by_rfid=Sum('batch_balloon_count'),
            total_balloon_count_by_ttn=Sum('amount_of_ttn'),
        )

    @classmethod
    def get_common_stats_for_gns(cls) -> list:
        """
        Собирает статистику по партиям за последние день и месяц
        """
        today = date.today()
        first_day_of_month = today.replace(day=1)

        month_start = datetime.combine(first_day_of_month, time.min)

        queryset = cls.objects.filter(begin_date__gte=month_start)

        # Группируем по reader_number
        stats_by_reader = defaultdict(lambda: {"truck_month": 0, "truck_today": 0})

        for batch in queryset:
            reader_id = batch.reader_number
            if reader_id is None:
                continue

            stats_by_reader[reader_id]["truck_month"] += 1
            if batch.begin_date >= today:
                stats_by_reader[reader_id]["truck_today"] += 1

        stats = [
            {"reader_id": reader_id, **data}
            for reader_id, data in stats_by_reader.items()
        ]
        return stats


class BalloonsUnloadingBatch(models.Model):
    """
    Партия баллонов для приёмки из транспорта.
    Содержит:
    - Временные метки начала/окончания погрузки
    - Данные транспорта (грузовик и прицеп)
    - Статистику по количеству баллонов (по объёмам и RFID)
    - Список принятых баллонов (ManyToMany)
    - Номер и количество по ТТН
    - Статус активности партии
    """
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

    def add_balloon(self, nfc_tag):
        """
        Добавляет баллон в партию по NFC-метке
        Возвращает словарь с результатами операции:
        {
            'success': bool,
            'balloon_id': int | None,
            'new_count': int,
            'error': str
        }
        """
        result = {
            'success': False,
            'balloon_id': None,
            'new_count': self.amount_of_rfid or 0,
            'error': 'ok'
        }

        try:
            if self.balloon_list.filter(nfc_tag=nfc_tag).exists():
                result['error'] = 'Баллон уже в партии'
                return result

            balloon = Balloon.objects.get(nfc_tag=nfc_tag)
            self.balloon_list.add(balloon)
            self.amount_of_rfid = (self.amount_of_rfid or 0) + 1
            self.save()

            result.update({
                'success': True,
                'balloon_id': balloon.nfc_tag,
                'new_count': self.amount_of_rfid
            })

        except Balloon.DoesNotExist:
            result['error'] = 'Баллон не найден'
        except Exception as e:
            result['error'] = f'Ошибка сервера: {str(e)}'

        return result

    def remove_balloon(self, nfc_tag):
        """
        Удаляет баллон из партии по NFC-метке
        Возвращает словарь с результатами операции:
        {
            'success': bool,
            'balloon_id': int | None,
            'new_count': int,
            'error': str
        }
        """
        result = {
            'success': False,
            'balloon_id': None,
            'new_count': self.amount_of_rfid or 0,
            'error': 'ok'
        }

        try:
            if not self.balloon_list.filter(nfc_tag=nfc_tag).exists():
                result['error'] = 'Баллон не найден в партии'
                return result

            balloon = Balloon.objects.get(nfc_tag=nfc_tag)
            self.balloon_list.remove(balloon)
            self.amount_of_rfid = max((self.amount_of_rfid or 0) - 1, 0)
            self.save()

            result.update({
                'success': True,
                'balloon_id': balloon.nfc_tag,
                'new_count': self.amount_of_rfid
            })

        except Balloon.DoesNotExist:
            result['error'] = 'Баллон не найден'
        except Exception as e:
            result['error'] = f'Ошибка сервера: {str(e)}'

        return result

    @classmethod
    def get_period_stats(cls, start_date: Optional[date]=None, end_date: Optional[date]=None) -> Dict[str, Optional[int]]:
        """
        Собирает статистику по партиям за период:
        - кол-во партий
        - кол-во баллонов с RFID
        - кол-во баллонов по ТТН
        """
        queryset = cls.objects.filter(begin_date__range=[start_date, end_date])

        return queryset.annotate(
            batch_balloon_count=Count('balloon_list'),
        ).aggregate(
            total_batches=Count('id'),
            total_balloon_count_by_rfid=Sum('batch_balloon_count'),
            total_balloon_count_by_ttn=Sum('amount_of_ttn'),
        )

    @classmethod
    def get_common_stats_for_gns(cls) -> list:
        """
        Собирает статистику по партиям за последние день и месяц
        """
        today = date.today()
        first_day_of_month = today.replace(day=1)

        month_start = datetime.combine(first_day_of_month, time.min)

        queryset = cls.objects.filter(begin_date__gte=month_start)

        # Группируем по reader_number
        stats_by_reader = defaultdict(lambda: {"truck_month": 0, "truck_today": 0})

        for batch in queryset:
            reader_id = batch.reader_number
            if reader_id is None:
                continue

            stats_by_reader[reader_id]["truck_month"] += 1
            if batch.begin_date >= today:
                stats_by_reader[reader_id]["truck_today"] += 1

        stats = [
            {"reader_id": reader_id, **data}
            for reader_id, data in stats_by_reader.items()
        ]
        return stats
