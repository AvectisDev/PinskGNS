"""Модели грузовиков и прицепов."""

import re

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

BELARUS_MOBILE_PHONE_RE = re.compile(r'^\+375\((25|29|33|44)\)\d{3}-\d{2}-\d{2}$')
BELARUS_MOBILE_PHONE_HELP = 'Формат: +375(29)123-45-78. Код оператора: 25, 29, 33 или 44.'


def validate_belarus_mobile_phone(value: str) -> None:
    """Проверяет белорусский мобильный номер; пустое значение допустимо."""
    if not value:
        return
    if not BELARUS_MOBILE_PHONE_RE.fullmatch(value):
        raise ValidationError(BELARUS_MOBILE_PHONE_HELP)


class TruckType(models.Model):
    """Справочник типов грузового транспорта (Клетевоз, Трал и др.)"""
    type = models.CharField(max_length=100, verbose_name="Тип грузовика")

    def __str__(self):
        """Возвращает название типа грузовика."""
        return self.type

    class Meta:
        """Метаданные справочника типов грузовиков."""
        verbose_name = "Тип грузовика"
        verbose_name_plural = "Типы грузовиков"


class Driver(models.Model):
    """Справочник водителей. Заполняется в админке, выбирается у грузовика."""

    last_name = models.CharField(max_length=50, verbose_name="Фамилия")
    first_name = models.CharField(max_length=50, verbose_name="Имя")
    middle_name = models.CharField(max_length=50, blank=True, default="", verbose_name="Отчество")
    phone = models.CharField(
        max_length=17,
        blank=True,
        default="",
        verbose_name="Телефон",
        help_text=BELARUS_MOBILE_PHONE_HELP,
        validators=[validate_belarus_mobile_phone],
    )
    comment = models.TextField(blank=True, default="", verbose_name="Комментарий")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    def __str__(self):
        """Возвращает ФИО водителя."""
        parts = [self.last_name, self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        return ' '.join(parts)

    class Meta:
        """Метаданные справочника водителей."""
        verbose_name = "Водитель"
        verbose_name_plural = "Водители"
        ordering = ["last_name", "first_name"]


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
    driver = models.OneToOneField(
        Driver,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="truck",
        verbose_name="Водитель",
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
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    entry_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата и время въезда")
    departure_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата и время выезда")

    def clean(self):
        """Нормализует регистрационный номер к канону display."""
        super().clean()
        if self.registration_number:
            from transport.registration import canonicalize_registration_number
            self.registration_number = canonicalize_registration_number(self.registration_number)

    def save(self, *args, **kwargs):
        """Сохраняет грузовик с каноническим регистрационным номером."""
        if self.registration_number:
            from transport.registration import canonicalize_registration_number
            self.registration_number = canonicalize_registration_number(self.registration_number)
        super().save(*args, **kwargs)

    def __str__(self):
        """Регистрационный знак грузовика."""
        return self.registration_number

    class Meta:
        """Метаданные модели грузовика."""
        verbose_name = "Грузовик"
        verbose_name_plural = "Грузовики"
        ordering = ['-is_on_station', '-entry_at']

    def get_absolute_url(self):
        """URL страницы просмотра грузовика."""
        return reverse('transport:truck_detail', args=[self.pk])

    def get_update_url(self):
        """URL страницы редактирования грузовика."""
        return reverse('transport:truck_update', args=[self.pk])

    def get_delete_url(self):
        """URL страницы удаления грузовика."""
        return reverse('transport:truck_delete', args=[self.pk])


class TrailerType(models.Model):
    """Справочник типов прицепов (Прицеп бортовой, Полуприцеп и др.)"""
    type = models.CharField(max_length=100, verbose_name="Тип прицепа")

    def __str__(self):
        """Возвращает название типа прицепа."""
        return self.type

    class Meta:
        """Метаданные справочника типов прицепов."""
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
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    entry_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата и время въезда")
    departure_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата и время выезда")

    def clean(self):
        """Нормализует регистрационный номер к канону display."""
        super().clean()
        if self.registration_number:
            from transport.registration import canonicalize_registration_number
            self.registration_number = canonicalize_registration_number(self.registration_number)

    def save(self, *args, **kwargs):
        """Сохраняет прицеп с каноническим регистрационным номером."""
        if self.registration_number:
            from transport.registration import canonicalize_registration_number
            self.registration_number = canonicalize_registration_number(self.registration_number)
        super().save(*args, **kwargs)

    def __str__(self):
        """Регистрационный знак прицепа."""
        return self.registration_number

    class Meta:
        """Метаданные модели прицепа."""
        verbose_name = "Прицеп"
        verbose_name_plural = "Прицепы"
        ordering = ['-is_on_station', '-entry_at']

    def get_absolute_url(self):
        """URL страницы просмотра прицепа."""
        return reverse('transport:trailer_detail', args=[self.pk])

    def get_update_url(self):
        """URL страницы редактирования прицепа."""
        return reverse('transport:trailer_update', args=[self.pk])

    def get_delete_url(self):
        """URL страницы удаления прицепа."""
        return reverse('transport:trailer_delete', args=[self.pk])
