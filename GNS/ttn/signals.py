from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import RailwayTtn, AutoTtn, BalloonTtn
from .tasks import generate_1c_file

from django.db.models.signals import m2m_changed

@receiver(m2m_changed, sender=RailwayTtn.railway_tank_list.through)
def trigger_1c_file_on_tanks_added(sender, instance, action, **kwargs):
    if action == "post_add":
        print(f"[Сигнал] Цистерны добавлены в ТТН: {instance.number}")
        print(f"Текущие цистерны: {list(instance.railway_tank_list.all())}")
        generate_1c_file.delay(instance.number)

@receiver(m2m_changed, sender=AutoTtn)
def trigger_1c_file_for_auto_gas(sender, instance, action, **kwargs):
    """Для автоцистерн"""
    if action == "post_add":
        print(f"[Сигнал] автоцистерны добавлены в ТТН: {instance.number}")
        print(f"Текущие цистерны: {list(instance.railway_tank_list.all())}")
        generate_1c_file.delay(instance.number)

@receiver(m2m_changed, sender=BalloonTtn)
def trigger_1c_file_for_balloons(sender, instance, action, **kwargs):
    """Для баллонов"""
    if action == "post_add":
        print(f"[Сигнал] баллоны добавлены в ТТН: {instance.number}")
        print(f"Текущие цистерны: {list(instance.railway_tank_list.all())}")
        generate_1c_file.delay(instance.number)
