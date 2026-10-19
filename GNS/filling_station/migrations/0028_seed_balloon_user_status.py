from django.db import migrations

# Сид только для миграции — не использовать в runtime-коде.
BALLOON_USER_STATUS_SEED = [
    'Создание паспорта баллона',
    'Наполнение баллона сжиженным газом',
    'Погрузка полного баллона в кассету',
    'Погрузка полного баллона в трал',
    'Погрузка пустого баллона в кассету',
    'Погрузка пустого баллона в трал',
    'Регистрация полного баллона на складе',
    'Регистрация пустого баллона на складе',
    'Снятие пустого баллона у потребителя',
    'Установка баллона потребителю',
    'Принятие баллона от другой организации',
    'Снятие RFID метки',
    'Установка новой RFID метки',
    'Редактирование паспорта баллона',
    'Покраска',
    'Техническое освидетельствование',
    'Выбраковка',
    'Утечка газа',
    'Опорожнение(слив) баллона',
    'Контрольное взвешивание',
]


def seed_balloon_user_statuses(apps, schema_editor):
    """Заполняет справочник статусов баллона начальным набором."""
    BalloonUserStatus = apps.get_model('filling_station', 'BalloonUserStatus')
    for name in BALLOON_USER_STATUS_SEED:
        BalloonUserStatus.objects.update_or_create(
            name=name,
            defaults={'is_active': True},
        )


def unseed_balloon_user_statuses(apps, schema_editor):
    """Удаляет записи, созданные сидом."""
    BalloonUserStatus = apps.get_model('filling_station', 'BalloonUserStatus')
    BalloonUserStatus.objects.filter(name__in=BALLOON_USER_STATUS_SEED).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0027_balloon_user_status'),
    ]

    operations = [
        migrations.RunPython(seed_balloon_user_statuses, unseed_balloon_user_statuses),
    ]
