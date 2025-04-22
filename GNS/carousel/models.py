from django.db import models
from django.contrib.auth.models import User


BALLOON_SIZE_CHOICES = [
    (5, 5),
    (12, 12),
    (27, 27),
    (50, 50),
]

class Carousel(models.Model):
    carousel_number = models.IntegerField(default=1, verbose_name="Номер карусели наполнения")
    is_empty = models.BooleanField(default=False, verbose_name="Принят запрос на наполнение баллона")
    post_number = models.IntegerField(verbose_name="Номер поста наполнения")
    empty_weight = models.FloatField(null=True, blank=True, verbose_name="Вес пустого баллона на посту")
    full_weight = models.FloatField(null=True, blank=True, verbose_name="Вес полного баллона на посту")
    nfc_tag = models.CharField(null=True, blank=True, max_length=30, verbose_name="Номер метки")
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
        return self.nfc_tag

    class Meta:
        verbose_name = "Карусель"
        verbose_name_plural = "Карусель"
        ordering = ['-change_date', '-change_time']


class CarouselSettings(models.Model):
    read_only = models.BooleanField(default=True, verbose_name="Только чтение с постов наполнения")
    use_weight_management = models.BooleanField(default=False, verbose_name="Использовать коррекцию веса")
    use_common_correction = models.BooleanField(default=False, verbose_name="Использовать общее значение коррекции веса")
    weight_correction_value = models.FloatField(default=0.0, verbose_name="Значение корректировки веса")
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

    def __int__(self):
        return self.pk

    def __str__(self):
        return 'Карусель'

    class Meta:
        verbose_name = "Настройки карусели"
        verbose_name_plural = "Настройки карусели"
