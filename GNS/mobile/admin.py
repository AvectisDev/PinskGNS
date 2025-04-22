from django.contrib import admin
from django.utils.html import format_html
from .models import MobileApp


@admin.register(MobileApp)
class MobileAppAdmin(admin.ModelAdmin):
    list_display = ['version_name', 'apk_file_link', 'update_date']
    readonly_fields = ['update_date']
    list_filter = ['update_date']
    search_fields = ['version_name']

    def apk_file_link(self, obj):
        if obj.apk_file:
            return format_html('<a href="{0}">Скачать APK</a>', obj.apk_file.url)
        return "Нет файла"
    apk_file_link.short_description = "APK файл"
