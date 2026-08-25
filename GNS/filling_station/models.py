from collections import defaultdict
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.urls import reverse
from django.db.models import Q, F, Sum, Count, Case, When, IntegerField
from django.db.models.functions import Coalesce
from django.conf import settings
from typing import Dict, Any, Optional, List
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
    def get_all_readers_stats(cls, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """
        Получает статистику по всем считывателям за указанный период.
        Источник — DailyReaderCounter (те же счётчики, что и в RFID-таблицах).
        """
        period_stats = (
            DailyReaderCounter.objects.filter(
                day__gte=start_date,
                day__lte=end_date,
            )
            .values('number_id')
            .annotate(
                total_rfid=Sum('amount_of_rfid'),
                total_sensor=Sum('amount_of_sensor'),
            )
        )
        stats_by_reader = {
            row['number_id']: row for row in period_stats
        }

        result: List[Dict[str, Any]] = []
        for reader in ReaderSettings.objects.order_by('number'):
            counter = stats_by_reader.get(reader.number, {})
            total_rfid = counter.get('total_rfid') or 0
            total_sensor = counter.get('total_sensor') or 0
            result.append({
                'number': reader.number,
                'status': reader.status,
                'total_rfid': total_rfid,
                'total_sensor': total_sensor,
                'total_balloons': total_rfid + total_sensor,
            })
        return result

class DailyReaderCounter(models.Model):
    """
    Ежедневные счетчики по конкретному ридеру
    """
    number = models.ForeignKey(
        ReaderSettings,
        on_delete=models.PROTECT,
        verbose_name="Номер считывателя",
        related_name='daily_counters'
    )
    day = models.DateField(verbose_name="Дата", db_index=True)
    amount_of_rfid = models.IntegerField(default=0, verbose_name="Баллонов по RFID")
    amount_of_sensor = models.IntegerField(default=0, verbose_name="Баллонов по сенсору")
    change_at = models.DateTimeField(auto_now=True, verbose_name="Дата последнего изменения")

    def __str__(self):
        return f'Количество баллонов на ридере {self.number}'

    class Meta:
        verbose_name = "Счетчики по ридерам за день"
        verbose_name_plural = "Счетчики по ридерам за день"
        ordering = ['-day']
        constraints = [
            models.UniqueConstraint(fields=['number', 'day'], name='uniq_number_day'),
        ]

    @classmethod
    def add_rfid(cls, reader: ReaderSettings):
        obj, created = cls.objects.get_or_create(
            number=reader,
            day=timezone.localdate(),
            defaults={'amount_of_rfid': 0, 'amount_of_sensor': 0}
        )
        # атомарный инкремент:
        cls.objects.filter(pk=obj.pk).update(
            amount_of_rfid=F('amount_of_rfid') + 1,
            change_at=timezone.now()
        )

    @classmethod
    def add_sensor(cls, reader: ReaderSettings):
        obj, created = cls.objects.get_or_create(
            number=reader,
            day=timezone.localdate(),
            defaults={'amount_of_rfid': 0, 'amount_of_sensor': 0}
        )
        cls.objects.filter(pk=obj.pk).update(
            amount_of_sensor=F('amount_of_sensor') + 1,
            change_at=timezone.now()
        )

    @classmethod
    def get_reader_period_stats(cls, reader: ReaderSettings, start_date: date, end_date: date) -> dict:
        """
        Получение статистики по конкретному ридеру за указанный период.
        Возвращает словарь с количеством баллонов по RFID и по сенсору.
        """
        stats = cls.objects.filter(
            number=reader,
            day__gte=start_date,
            day__lte=end_date
        ).aggregate(
            total_rfid=Sum('amount_of_rfid'),
            total_sensor=Sum('amount_of_sensor')
        )
        
        return {
            'total_rfid': stats.get('total_rfid', 0) or 0,
            'total_sensor': stats.get('total_sensor', 0) or 0
        }

    @classmethod
    def get_common_stats_for_gns(cls) -> list:
        """
        Получение статистики по ридерам за месяц и сегодня.
        Возвращает список словарей с данными по каждому ридеру.
        balloons_month/balloons_today - только баллоны, подсчитанные сенсором (amount_of_sensor)
        rfid_month/rfid_today - только баллоны, подсчитанные по RFID (amount_of_rfid)
        """
        today = timezone.localdate()
        first_day_of_month = today.replace(day=1)

        # Получаем агрегированные данные за месяц
        month_stats = cls.objects.filter(
            day__gte=first_day_of_month
        ).values('number__number').annotate(
            rfid_month=Sum('amount_of_rfid'),
            balloons_month=Sum('amount_of_sensor')
        )

        # Получаем агрегированные данные за сегодня
        today_stats = cls.objects.filter(
            day=today
        ).values('number__number').annotate(
            rfid_today=Sum('amount_of_rfid'),
            balloons_today=Sum('amount_of_sensor')
        )

        # Преобразуем в словари для быстрого доступа
        month_dict = {stat['number__number']: stat for stat in month_stats}
        today_dict = {stat['number__number']: stat for stat in today_stats}

        stats = []
        for reader in ReaderSettings.objects.all():
            reader_id = reader.number
            month = month_dict.get(reader_id, {})
            today = today_dict.get(reader_id, {})

            stats.append({
                "reader_id": reader_id,
                "balloons_month": month.get('balloons_month', 0) or 0,
                "rfid_month": month.get('rfid_month', 0) or 0,
                "balloons_today": today.get('balloons_today', 0) or 0,
                "rfid_today": today.get('rfid_today', 0) or 0,
            })

        return stats


class TotalReadersCounter(models.Model):
    """
    Свод по складу. Можно хранить ручные базовые значения (от которых ведется отсчет).
    """
    total_empty = models.IntegerField(default=0, verbose_name="Всего пустых баллонов")
    total_full = models.IntegerField(default=0, verbose_name="Всего полных баллонов")
    changed_at = models.DateTimeField(auto_now=True, verbose_name='Дата последнего изменения')

    class Meta:
        verbose_name = "Свод по складу"
        verbose_name_plural = "Свод по складу"
        ordering = ['-changed_at']

    def __str__(self):
        return f'Свод (E={self.total_empty}, F={self.total_full})'

    @classmethod
    def add_full_balloon(cls):
        cls.objects.filter(pk=1).update(total_full=F('total_full') + 1, changed_at=timezone.now())

    @classmethod
    def add_empty_balloon(cls):
        cls.objects.filter(pk=1).update(total_empty=F('total_empty') + 1, changed_at=timezone.now())

    @classmethod
    def sub_full_balloon(cls):
        cls.objects.filter(pk=1, total_full__gt=0).update(total_full=F('total_full') - 1, changed_at=timezone.now())

    @classmethod
    def sub_empty_balloon(cls):
        cls.objects.filter(pk=1, total_empty__gt=0).update(total_empty=F('total_empty') - 1, changed_at=timezone.now())

    @classmethod
    def insert_manual_values(cls, empty: int = None, full: int = None):
        """Ввод значений со SCADA системы"""
        cls.objects.filter(pk=1).update(
            total_empty=empty if empty is not None else F('total_empty'),
            total_full=full if full is not None else F('total_full'),
            changed_at=timezone.now()
        )

    @classmethod
    def get_balloons_stats(cls):
        """
        Получение статистики полных и пустых баллонов на станции.
        Возвращает словарь с количеством полных и пустых баллонов.
        """
        counter = cls.objects.filter(pk=1).first()
        if counter:
            return {
                'filled': counter.total_full,
                'empty': counter.total_empty
            }
        return {
            'filled': 0,
            'empty': 0
        }


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
    registration_number = models.CharField(unique=True, max_length=10, verbose_name="Регистрационный знак")
    type = models.ForeignKey(
        TruckType,
        on_delete=models.PROTECT,
        verbose_name="Тип",
        default=1
    )
    capacity_cylinders = models.IntegerField(null=True, blank=True, verbose_name="Максимальная вместимость баллонов")
    max_weight_of_transported_cylinders = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Максимальная масса перевозимых баллонов"
        )
    max_mass_of_transported_gas = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Максимальная масса перевозимого газа"
        )
    max_gas_volume = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Максимальный объём перевозимого газа"
        )
    empty_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Вес пустого т/с (по техпаспорту)"
        )
    full_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Вес полного т/с (по техпаспорту)"
        )
    is_on_station = models.BooleanField(default=False, verbose_name="Находится на станции")
    entry_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата и время въезда")
    departure_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата и время выезда")

    def __str__(self):
        return self.registration_number

    class Meta:
        verbose_name = "Грузовик"
        verbose_name_plural = "Грузовики"
        ordering = ['-is_on_station', '-entry_at']

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
        on_delete=models.PROTECT,
        verbose_name="Автомобиль",
        related_name='trailer',
        default=1
    )
    trailer_brand = models.CharField(null=True, blank=True, max_length=20, verbose_name="Марка прицепа")
    registration_number = models.CharField(unique=True, max_length=10, verbose_name="Регистрационный знак")
    type = models.ForeignKey(
        TrailerType,
        on_delete=models.PROTECT,
        verbose_name="Тип",
        default=1
    )
    capacity_cylinders = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Максимальная вместимость баллонов"
        )
    max_weight_of_transported_cylinders = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Максимальная масса перевозимых баллонов"
        )
    max_mass_of_transported_gas = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Максимальная масса перевозимого газа"
        )
    max_gas_volume = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Максимальный объём перевозимого газа"
        )
    empty_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Вес пустого т/с (по техпаспорту)"
        )
    full_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Вес полного т/с (по техпаспорту)"
        )
    is_on_station = models.BooleanField(default=False, verbose_name="Находится на станции")
    entry_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата и время въезда")
    departure_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата и время выезда")

    def __str__(self):
        return self.registration_number

    class Meta:
        verbose_name = "Прицеп"
        verbose_name_plural = "Прицепы"
        ordering = ['-is_on_station', '-entry_at']

    def get_absolute_url(self):
        return reverse('filling_station:trailer_detail', args=[self.pk])

    def get_update_url(self):
        return reverse('filling_station:trailer_update', args=[self.pk])

    def get_delete_url(self):
        return reverse('filling_station:trailer_delete', args=[self.pk])


class BatchStatus(models.TextChoices):
    ACTIVE = 'active', 'В работе'
    PAUSED = 'paused', 'Приостановлена'
    COMPLETED = 'completed', 'Завершена'
    MIRIADA_ERROR = 'miriada_error', 'Завершена, ошибка Мириады'


class BalloonsBatch(models.Model):
    """
    Партии баллонов. Содержит:
    - Временные метки начала/окончания партии
    - Данные транспорта (грузовик и прицеп)
    - Статистику по количеству баллонов (по объёмам и RFID)
    - Список загруженных баллонов (ManyToMany)
    - Номер и количество по ТТН
    - Статус партии (active / paused / completed / miriada_error)
    """
    batch_type = models.CharField(choices=settings.BATCH_TYPE_CHOICES, default='l', verbose_name="Тип партии")
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата и время начала")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата и время окончания")
    truck = models.ForeignKey(
        Truck,
        on_delete=models.PROTECT,
        verbose_name="Автомобиль"
    )
    trailer = models.ForeignKey(
        Trailer,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Прицеп"
    )
    reader_number = models.IntegerField(null=True, blank=True, verbose_name="Номер считывателя")
    amount_of_rfid = models.IntegerField(default=0, verbose_name="Количество баллонов по rfid")
    amount_of_sensor = models.IntegerField(default=0, verbose_name="Количество баллонов по датчику")
    amount_of_ttn = models.IntegerField(
        default=0,
        verbose_name="Количество баллонов по электронной ТТН",
    )
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
    status = models.CharField(
        max_length=20,
        choices=BatchStatus.choices,
        default=BatchStatus.PAUSED,
        verbose_name="Статус партии",
        db_index=True,
    )
    miriada_close_failed = models.BooleanField(
        default=False,
        verbose_name="Ошибка закрытия ТТН в Мириаде",
    )
    miriada_error_message = models.CharField(
        null=True,
        blank=True,
        max_length=200,
        verbose_name="Текст ошибки при неудачном закрытии ТТН"
    )
    miriada_balloons_sent = models.BooleanField(
        default=False,
        verbose_name="Статусы баллонов отправлены в Мириаду",
    )
    ttn_id = models.IntegerField(verbose_name="ID ТТН")
    balloons_type = models.CharField(choices=settings.BALLOON_TYPE_CHOICES, default='e', verbose_name="Пустой/полный")
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        default=1,
        verbose_name="Пользователь"
    )

    def __str__(self):
        return f'Партия №{self.id}. Тип {self.batch_type}'

    class Meta:
        verbose_name = "Партия баллонов"
        verbose_name_plural = "Партии баллонов"
        ordering = ['-started_at']

    def _batch_url_prefix(self) -> str:
        return 'balloon_loading_batch' if self.batch_type == 'l' else 'balloon_unloading_batch'

    def get_absolute_url(self):
        return reverse(f'filling_station:{self._batch_url_prefix()}_detail', args=[self.pk])

    def get_update_url(self):
        return reverse(f'filling_station:{self._batch_url_prefix()}_update', args=[self.pk])

    def get_delete_url(self):
        return reverse(f'filling_station:{self._batch_url_prefix()}_delete', args=[self.pk])

    def get_retry_close_url(self):
        return reverse(f'filling_station:{self._batch_url_prefix()}_retry_close', args=[self.pk])

    def can_retry_miriada_close(self) -> bool:
        return self.status == BatchStatus.MIRIADA_ERROR and bool(self.ttn_id)

    def accepts_rfid(self) -> bool:
        return self.status == BatchStatus.ACTIVE

    def accepts_manual_edits(self) -> bool:
        return self.status in (BatchStatus.ACTIVE, BatchStatus.PAUSED)

    def save(self, *args, **kwargs):
        if self.status == BatchStatus.MIRIADA_ERROR:
            self.miriada_close_failed = True
        elif self.status == BatchStatus.COMPLETED:
            self.miriada_close_failed = False
        super().save(*args, **kwargs)

    def get_ttn_name(self) -> Optional[str]:
        """Номер ТТН из Мириады по сохранённому ttn_id"""
        if not self.ttn_id:
            return None
        from ttn.models import MiriadaTtn
        return MiriadaTtn.objects.filter(ttn_id=self.ttn_id).values_list('name', flat=True).first()

    def get_amount_without_rfid(self) -> int:
        """Количество баллонов без RFID: сумма полей объёмов (50л — баллоны без метки на приёмке)."""
        return (
            (self.amount_of_5_liters or 0)
            + (self.amount_of_12_liters or 0)
            + (self.amount_of_27_liters or 0)
            + (self.amount_of_50_liters or 0)
        )

    def add_balloon(self, nfc_tag: str = None) -> dict:
        """
        Добавляет баллон в партию по NFC-метке. Добавляет общее количество баллонов, посчитанное оптическим датчиком.
        Возвращает словарь с результатами операции:
        {
            'success': bool,
            'balloon_id': str | None,
            'message': str
        }
        """
        result = {
            'success': False,
            'balloon_id': None,
            'message': 'ok'
        }

        if not self.accepts_manual_edits():
            result['message'] = 'Партия не принимает изменения в текущем статусе'
            return result

        # Добавляем баллон, прошедший через оптический датчик
        if not nfc_tag:
            if not self.accepts_rfid():
                result['message'] = 'Оптический датчик учитывается только у активной партии'
                return result
            self.amount_of_sensor = (self.amount_of_sensor or 0) + 1
            self.save()
            result['success'] = True
            return result

        try:
            if self.balloon_list.filter(nfc_tag=nfc_tag).exists():
                result['message'] = f'Баллон с меткой {nfc_tag} уже в партии'
                return result

            balloon = Balloon.objects.get(nfc_tag=nfc_tag)
            self.balloon_list.add(balloon)
            self.amount_of_rfid = (self.amount_of_rfid or 0) + 1
            self.save()

            result.update({
                'success': True,
                'balloon_id': balloon.nfc_tag,
            })

        except Balloon.DoesNotExist:
            result['message'] = f'Баллон с меткой {nfc_tag} не найден'
        except Exception as e:
            result['message'] = f'Ошибка сервера: {str(e)}'

        return result

    def remove_balloon(self, nfc_tag) -> dict:
        """
        Удаляет баллон из партии по NFC-метке. Возвращает словарь с результатами операции:
        {
            'success': bool,
            'balloon_id': str | None,
            'message': str
        }
        """
        result = {
            'success': False,
            'balloon_id': None,
            'message': 'ok'
        }

        if not self.accepts_manual_edits():
            result['message'] = 'Партия не принимает изменения в текущем статусе'
            return result

        try:
            if not self.balloon_list.filter(nfc_tag=nfc_tag).exists():
                result['message'] = f'Баллон с меткой {nfc_tag} не найден в партии'
                return result

            balloon = Balloon.objects.get(nfc_tag=nfc_tag)
            self.balloon_list.remove(balloon)
            self.amount_of_rfid = max((self.amount_of_rfid or 0) - 1, 0)
            self.save()

            result.update({
                'success': True,
                'balloon_id': balloon.nfc_tag,
            })

        except Balloon.DoesNotExist:
            result['message'] = f'Баллон с меткой {nfc_tag} не найден'
        except Exception as e:
            result['message'] = f'Ошибка сервера: {str(e)}'

        return result

    @classmethod
    def get_period_stats(
        cls,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        batch_type: Optional[str] = None,
    ) -> Dict[str, int]:
        """
        Собирает статистику по партиям за период:
        - кол-во партий
        - кол-во баллонов с RFID
        - кол-во баллонов по ТТН (датчик или сумма объёмов)
        """
        queryset = cls.objects.all()
        if start_date is not None and end_date is not None:
            queryset = queryset.filter(
                started_at__date__gte=start_date,
                started_at__date__lte=end_date,
            )
        if batch_type:
            queryset = queryset.filter(batch_type=batch_type)

        ttn_amount = Case(
            When(amount_of_sensor__gt=0, then=F('amount_of_sensor')),
            default=(
                Coalesce(F('amount_of_5_liters'), 0)
                + Coalesce(F('amount_of_12_liters'), 0)
                + Coalesce(F('amount_of_27_liters'), 0)
                + Coalesce(F('amount_of_50_liters'), 0)
            ),
            output_field=IntegerField(),
        )

        stats = queryset.aggregate(
            total_batches=Count('id'),
            total_balloon_count_by_rfid=Coalesce(Sum('amount_of_rfid'), 0),
            total_balloon_count_by_ttn=Coalesce(Sum(ttn_amount), 0),
        )
        return {
            'total_batches': stats['total_batches'] or 0,
            'total_balloon_count_by_rfid': stats['total_balloon_count_by_rfid'] or 0,
            'total_balloon_count_by_ttn': stats['total_balloon_count_by_ttn'] or 0,
        }

    @classmethod
    def get_common_stats_for_gns(cls, batch_type: Optional[str] = None) -> list:
        """
        Собирает статистику по партиям за последние день и месяц
        """
        now = timezone.localtime()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Фильтруем по месяцу
        queryset = cls.objects.filter(started_at__gte=month_start)
        
        if batch_type:
            queryset = queryset.filter(batch_type=batch_type)

        stats_by_reader = defaultdict(lambda: {"truck_month": 0, "truck_today": 0})

        for batch in queryset:
            reader_id = batch.reader_number
            if reader_id is None:
                continue

            stats_by_reader[reader_id]["truck_month"] += 1
            
            # Все datetime теперь aware (с часовым поясом)
            if batch.started_at >= today_start:
                stats_by_reader[reader_id]["truck_today"] += 1

        stats = [
            {"reader_id": reader_id, **data}
            for reader_id, data in stats_by_reader.items()
        ]
        return stats
