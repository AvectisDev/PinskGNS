from django.db import models
from django.core.exceptions import ValidationError


class MobileApp(models.Model):
    version_name = models.CharField(max_length=10, unique=True, verbose_name="Номер версии")
    apk_file = models.FileField(upload_to='apk/', verbose_name="APK файл")
    update_date = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Версия мобильного приложения"
        verbose_name_plural = "Версии мобильного приложения"
        ordering = ['-update_date']

    def __str__(self):
        return f"Версия {self.version_name}"

    def clean(self):
        super().clean()
        if MobileApp.objects.filter(version_name=self.version_name).exclude(pk=self.pk).exists():
            raise ValidationError({'version_name': 'Версия с таким номером уже существует!'})
