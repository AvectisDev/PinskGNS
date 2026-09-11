from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.conf import settings


class Carousel(models.Model):
    """Запись о наполнении баллона на посте карусели."""

    carousel_number = models.IntegerField(default=1, verbose_name="Номер карусели наполнения")
    is_empty = models.BooleanField(default=False, verbose_name="Принят запрос на наполнение баллона")
    post_number = models.IntegerField(verbose_name="Номер поста наполнения")
    empty_weight = models.FloatField(null=True, blank=True, verbose_name="Вес пустого баллона на посту")
    full_weight = models.FloatField(null=True, blank=True, verbose_name="Вес полного баллона на посту")
    nfc_tag = models.CharField(null=True, blank=True, max_length=30, verbose_name="Номер метки")
    serial_number = models.CharField(null=True, blank=True, max_length=30, verbose_name="Серийный номер")
    size = models.IntegerField(choices=settings.BALLOON_SIZE_CHOICES, default=50, verbose_name="Объём")
    netto = models.FloatField(null=True, blank=True, verbose_name="Вес пустого баллона")
    brutto = models.FloatField(null=True, blank=True, verbose_name="Вес наполненного баллона")
    filling_status = models.BooleanField(default=False, verbose_name="Готов к наполнению")
    change_at = models.DateTimeField(auto_now=True, verbose_name="Дата и время изменений")

    def __int__(self):
        return self.pk

    def __str__(self):
        return self.nfc_tag if self.nfc_tag else 'Нет'

    class Meta:
        verbose_name = "Карусель"
        verbose_name_plural = "Карусель"
        ordering = ['-change_at']


class CarouselSettings(models.Model):
    """
    Настройки одной карусели: оборудование (NPort, RFID) и весовая политика.

    Одна запись = одна карусель. Поле ``number`` — бизнес-номер (unique), не PK.
    """

    number = models.IntegerField(unique=True, verbose_name="Номер карусели")
    name = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name="Название",
    )
    tcp_host = models.CharField(
        max_length=15,
        blank=True,
        default='',
        verbose_name="IP NPort",
    )
    tcp_port = models.IntegerField(default=4001, verbose_name="TCP-порт NPort")
    rfid_reader = models.ForeignKey(
        'filling_station.ReaderSettings',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='carousels',
        verbose_name="RFID-считыватель",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активна (listener)",
    )
    classify_size_by_weight = models.BooleanField(
        default=False,
        verbose_name="Определять объём (27/50) по весу пустого баллона",
    )
    size_27_empty_weight_max_g = models.PositiveIntegerField(
        default=16000,
        verbose_name="Макс. вес пустого 27 л, г",
    )

    read_only = models.BooleanField(default=True, verbose_name="Только чтение с постов наполнения")
    use_weight_management = models.BooleanField(default=False, verbose_name="Использовать коррекцию веса")
    use_common_correction = models.BooleanField(default=False, verbose_name="Использовать общее значение коррекции веса")
    weight_correction_value = models.FloatField(default=0.0, verbose_name="Значение корректировки веса")
    min_balloon_weight_from = models.FloatField(default=15.6, verbose_name="Минимальный вес баллона (от)")
    min_balloon_weight_to = models.FloatField(default=17.8, verbose_name="Минимальный вес баллона (до)")
    max_balloon_weight_from = models.FloatField(default=44.0, verbose_name="Максимальный вес баллона (от)")
    max_balloon_weight_to = models.FloatField(default=46.5, verbose_name="Максимальный вес баллона (до)")
    passport_weight_diff_from = models.FloatField(default=0.0, verbose_name="Разница паспортных весов (от)")
    passport_weight_diff_to = models.FloatField(default=21.5, verbose_name="Разница паспортных весов (до)")
    post_1_correction = models.FloatField(default=0.0, verbose_name="Корректор для 1 поста")
    post_2_correction = models.FloatField(default=0.0, verbose_name="Корректор для 2 поста")
    post_3_correction = models.FloatField(default=0.0, verbose_name="Корректор для 3 поста")
    post_4_correction = models.FloatField(default=0.0, verbose_name="Корректор для 4 поста")
    post_5_correction = models.FloatField(default=0.0, verbose_name="Корректор для 5 поста")
    post_6_correction = models.FloatField(default=0.0, verbose_name="Корректор для 6 поста")
    post_7_correction = models.FloatField(default=0.0, verbose_name="Корректор для 7 поста")
    post_8_correction = models.FloatField(default=0.0, verbose_name="Корректор для 8 поста")
    post_9_correction = models.FloatField(default=0.0, verbose_name="Корректор для 9 поста")
    post_10_correction = models.FloatField(default=0.0, verbose_name="Корректор для 10 поста")
    post_11_correction = models.FloatField(default=0.0, verbose_name="Корректор для 11 поста")
    post_12_correction = models.FloatField(default=0.0, verbose_name="Корректор для 12 поста")
    post_13_correction = models.FloatField(default=0.0, verbose_name="Корректор для 13 поста")
    post_14_correction = models.FloatField(default=0.0, verbose_name="Корректор для 14 поста")
    post_15_correction = models.FloatField(default=0.0, verbose_name="Корректор для 15 поста")
    post_16_correction = models.FloatField(default=0.0, verbose_name="Корректор для 16 поста")
    post_17_correction = models.FloatField(default=0.0, verbose_name="Корректор для 17 поста")
    post_18_correction = models.FloatField(default=0.0, verbose_name="Корректор для 18 поста")
    post_19_correction = models.FloatField(default=0.0, verbose_name="Корректор для 19 поста")
    post_20_correction = models.FloatField(default=0.0, verbose_name="Корректор для 20 поста")
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Пользователь",
        default=1
    )

    def clean(self):
        super().clean()
        if self.is_active:
            errors = {}
            if not (self.tcp_host or '').strip():
                errors['tcp_host'] = (
                    'Для активной карусели необходимо указать IP NPort.'
                )
            if self.rfid_reader_id is None:
                errors['rfid_reader'] = (
                    'Для активной карусели необходимо указать RFID-считыватель.'
                )
            if errors:
                raise ValidationError(errors)

    def __int__(self):
        return self.pk

    def __str__(self):
        if self.name:
            return self.name
        return f'Карусель {self.number}'

    class Meta:
        verbose_name = "Настройки карусели"
        verbose_name_plural = "Настройки карусели"
        ordering = ['number']
