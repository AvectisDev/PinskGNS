import os
import logging
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from filling_station.models import BalloonsBatch
from ttn.models import FilePath, RailwayTtn, AutoTtn, EmailRecipient


logger = logging.getLogger('celery')


def _get_latest_by_number(queryset, ttn_number):
    matches = list(queryset.filter(number=ttn_number).order_by('-id')[:2])
    if not matches:
        return None
    if len(matches) > 1:
        logger.warning(
            f'Найдено несколько ТТН с номером {ttn_number}, используется id={matches[0].id}'
        )
    return matches[0]


class Command(BaseCommand):
    help = 'Generate 1C file'

    def handle(self, ttn_number=None, *args, **kwargs):
        now = timezone.now()
        today = now.strftime('%d.%m.%y')
        filename = f'ГНС{today}.txt'
        file_path = FilePath.objects.first()
        path = file_path.path if file_path and file_path.path else None

        content_1 = self.generate_railway_list(ttn_number=ttn_number)
        content_2 = self.generate_loading_auto_gas_list(ttn_number=ttn_number)
        content_3 = self.generate_unloading_auto_gas_list(ttn_number=ttn_number)
        content_4 = self.generate_balloon_loading_list(now)
        content_5 = self.generate_balloon_unloading_list(now)

        content = '\n'.join([content_1, content_2, content_3, content_4, content_5])

        if not path:
            logger.warning('Путь FilePath не задан, файл 1С не сохранён')
            return

        full_path = os.path.join(path, filename)
        with open(full_path, 'w', encoding='windows-1251') as file:
            file.write(content)

        self.send_email_with_attachment(
            file_path=full_path,
            ttn_number=ttn_number,
        )

    def get_recipient_list(self):
        """Получаем список активных email-адресов"""
        return list(EmailRecipient.objects.filter(active=True).values_list('email', flat=True))

    def send_email_with_attachment(self, file_path, ttn_number):
        """Отправка файла по почте"""
        try:
            subject = f'ТТН {ttn_number} от {timezone.now().strftime("%d.%m.%Y")}'
            body = f'Во вложении файл по ТТН {ttn_number}'
            recipient_list = self.get_recipient_list()

            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=recipient_list,
            )

            with open(file_path, 'rb') as file:
                email.attach(
                    filename=os.path.basename(file_path),
                    content=file.read(),
                    mimetype='text/plain'
                )
            email.send()
            logger.info(f"Письмо с ТТН {ttn_number} успешно отправлено на {len(recipient_list)} адресов")
        except Exception as e:
            logger.error(f"Ошибка отправки письма: {str(e)}")

    def generate_railway_list(self, ttn_number):
        lines = ['ГНС-ТТН1']
        logger.info(f'Внутри функции generate_railway_list. Номер ТТН - {ttn_number}')

        if not ttn_number:
            return '\n'.join(lines)

        try:
            ttn = _get_latest_by_number(
                RailwayTtn.objects.select_related('shipper'),
                ttn_number,
            )
            if ttn is None:
                logger.error(f'ТТН {ttn_number} не найдена!')
                return '\n'.join(lines)

            tanks = ttn.railway_tank_list.all()

            if not tanks.exists():
                logger.error(f"Нет цистерн для ТТН {ttn_number}")
                return '\n'.join(lines)

            ttn_date = ttn.date.strftime('%d.%m.%y') if ttn.date else timezone.now().strftime('%d.%m.%y')

            entry_dates = []
            for t in tanks:
                hist = t.tank_history.filter(railway_ttn=ttn.railway_ttn).order_by('arrival_at').first()
                if hist and hist.arrival_at:
                    entry_dates.append(hist.arrival_at)
            first_entry_date = min(entry_dates) if entry_dates else None
            entry_date_str = first_entry_date.strftime('%d.%m.%y') if first_entry_date else ""

            lines.append(
                f'{ttn.number};'
                f'{ttn_date};'
                f'{entry_date_str};'
                f'{ttn.shipper.name if ttn.shipper else ""};'
            )

            for tank in tanks:
                hist = tank.tank_history.filter(railway_ttn=ttn.railway_ttn).order_by('-arrival_at', '-departure_at').first()
                netto_weight_ttn = hist.netto_weight_ttn if hist and hist.netto_weight_ttn is not None else 0
                gas_weight = hist.gas_weight if hist and hist.gas_weight is not None else 0
                departure_date = hist.departure_at if hist else None
                gas_type = hist.gas_type if hist and hist.gas_type and hist.gas_type != "Не выбран" else ttn.gas_type
                lines.append(
                    f'{tank.registration_number};'
                    f'{gas_type};'
                    f'{netto_weight_ttn:.3f};'
                    f'{gas_weight:.3f};'
                    f'{departure_date.strftime("%d.%m.%y") if departure_date else ""};'
                    f'{""};'  # Пустая накладная возврата
                )

        except Exception as e:
            logger.error(f'Ошибка: {str(e)}')

        return '\n'.join(lines)

    def generate_loading_auto_gas_list(self, ttn_number):
        """Генерация данных для поставки газа автоцистерной (ГНС-ТТН2) по конкретной ТТН"""
        lines = ['ГНС-ТТН2']

        if not ttn_number:
            return '\n'.join(lines)

        try:
            ttn = _get_latest_by_number(
                AutoTtn.objects.select_related('shipper', 'batch__truck'),
                ttn_number,
            )
            if ttn is None:
                logger.error(f"ТТН {ttn_number} не найдена")
                return '\n'.join(lines)

            if not ttn.batch or ttn.batch.batch_type != 'l':
                return '\n'.join(lines)

            batch = ttn.batch
            lines.append(
                f'{ttn.number};'
                f'{ttn.date.strftime("%d.%m.%y") if ttn.date else ""};'
                f'{ttn.shipper.name if ttn.shipper else ""};'
                f'{batch.weight_gas_amount or 0:.3f};'
                f'{batch.gas_amount or 0:.3f};'
                f'{batch.truck.registration_number if batch.truck else ""};'
            )
        except Exception as e:
            logger.error(f"Ошибка обработки ТТН {ttn_number}: {str(e)}")

        return '\n'.join(lines)

    def generate_unloading_auto_gas_list(self, ttn_number):
        """Генерация данных для отгрузки газа автоцистерной (ГНС-ТТН3) по конкретной ТТН"""
        lines = ['ГНС-ТТН3']

        if not ttn_number:
            return '\n'.join(lines)

        try:
            ttn = _get_latest_by_number(
                AutoTtn.objects.select_related('consignee', 'batch__truck'),
                ttn_number,
            )
            if ttn is None:
                logger.error(f"ТТН {ttn_number} не найдена")
                return '\n'.join(lines)

            if not ttn.batch or ttn.batch.batch_type != 'u':
                return '\n'.join(lines)

            batch = ttn.batch
            lines.append(
                f'{ttn.number};'
                f'{ttn.date.strftime("%d.%m.%y") if ttn.date else ""};'
                f'{ttn.consignee.name if ttn.consignee else ""};'
                f'{batch.weight_gas_amount or 0:.3f};'
                f'{batch.gas_amount or 0:.3f};'
                f'{batch.truck.registration_number if batch.truck else ""};'
            )
        except Exception as e:
            logger.error(f"Ошибка обработки ТТН {ttn_number}: {str(e)}")

        return '\n'.join(lines)

    def generate_balloon_loading_list(self, day_for_search):
        batches = BalloonsBatch.objects.filter(
            batch_type='l',
            started_at__date=day_for_search.date(),
        ).select_related('truck')

        lines = ['ГНС-ТТН4']

        for batch in batches:
            try:
                ttn = batch.balloons_ttn_loading.select_related('shipper').first()
                if not ttn:
                    continue

                lines.append(f'{ttn.number};'
                             f'{ttn.date.strftime("%d.%m.%y") if ttn.date else ""};'
                             f'{ttn.shipper.name if ttn.shipper else ""};'
                             f'{batch.truck.registration_number if batch.truck else ""};')

                lines.append(f';'
                             f'Баллоны 50 л;'
                             f'{(batch.amount_of_rfid or 0) + (batch.amount_of_50_liters or 0)};'
                             f'0;'
                             f'0;')
                lines.append(f';'
                             f'Баллоны 27 л;'
                             f'{batch.amount_of_27_liters or 0};'
                             f'0;'
                             f'0;')
                lines.append(f';'
                             f'Баллоны 12 л;'
                             f'{batch.amount_of_12_liters or 0};'
                             f'0;'
                             f'0;')
                lines.append(f';'
                             f'Баллоны 5 л;'
                             f'{batch.amount_of_5_liters or 0};'
                             f'0;'
                             f'0;')
            except Exception as e:
                logger.error(f"Error processing loading batch {batch.id}: {str(e)}")
                continue

        return '\n'.join(lines)

    def generate_balloon_unloading_list(self, day_for_search):
        batches = BalloonsBatch.objects.filter(
            batch_type='u',
            started_at__date=day_for_search.date(),
        ).select_related('truck')

        lines = ['ГНС-ТТН5']

        for batch in batches:
            try:
                ttn = batch.balloons_ttn_unloading.select_related('shipper').first()
                if not ttn:
                    continue

                lines.append(f'{ttn.number};'
                             f'{ttn.date.strftime("%d.%m.%y") if ttn.date else ""};'
                             f'{ttn.shipper.name if ttn.shipper else ""};'
                             f'{batch.truck.registration_number if batch.truck else ""};')

                balloons = batch.balloon_list.all()
                total_gas_weight = 0
                total_balloon_weight = 0
                if balloons:
                    for balloon in balloons:
                        total_gas_weight += (balloon.brutto or 0) - (balloon.netto or 0)
                        total_balloon_weight += (balloon.brutto or 0)

                lines.append(f'СПБТ;'
                             f'Баллоны 50 л;'
                             f'{(batch.amount_of_rfid or 0) + (batch.amount_of_50_liters or 0)};'
                             f'{total_gas_weight};'
                             f'{total_balloon_weight};')
                lines.append(f'СПБТ;'
                             f'Баллоны 27 л;'
                             f'{batch.amount_of_27_liters or 0};'
                             f'0;'
                             f'0;')
                lines.append(f'СПБТ;'
                             f'Баллоны 12 л;'
                             f'{batch.amount_of_12_liters or 0};'
                             f'0;'
                             f'0;')
                lines.append(f'СПБТ;'
                             f'Баллоны 5 л;'
                             f'{batch.amount_of_5_liters or 0};'
                             f'0;'
                             f'0;')
            except Exception as e:
                logger.error(f"Error processing unloading batch {batch.id}: {str(e)}")
                continue

        return '\n'.join(lines)
