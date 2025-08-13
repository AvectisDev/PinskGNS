import os
import logging
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from filling_station.models import BalloonsUnloadingBatch, BalloonsLoadingBatch
from ttn.models import FilePath, RailwayTtn, AutoTtn, EmailRecipient


logger = logging.getLogger('celery')


class Command(BaseCommand):
    help = 'Generate 1C file'
    today = timezone.now().strftime('%d.%m.%y')
    day_for_search = timezone.now()

    def handle(self, ttn_number=None, *args, **kwargs):
        filename = f'ГНС{self.today}.txt'
        file_path = FilePath.objects.first()
        path = file_path.path if file_path and file_path.path else None

        content_1 = self.generate_railway_list(ttn_number=ttn_number)
        content_2 = self.generate_loading_auto_gas_list(ttn_number=ttn_number)
        content_3 = self.generate_unloading_auto_gas_list(ttn_number=ttn_number)
        content_4 = self.generate_balloon_loading_list()
        content_5 = self.generate_balloon_unloading_list()

        content = '\n'.join([content_1, content_2, content_3, content_4, content_5])

        if path:
            full_path = os.path.join(path, filename)
            with open(full_path, 'w', encoding='windows-1251') as file:
                file.write(content)
            
            # Отправка почты
            self.send_email_with_attachment(
                file_path=full_path,
                ttn_number=ttn_number
        )
        else:
            # Логика для обмена по API
            pass

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

        try:
            ttn = RailwayTtn.objects.get(number=ttn_number)
            tanks = ttn.railway_tank_list.all()

            if not tanks.exists():
                logger.error(f"Нет цистерн для ТТН {ttn_number}")
                return '\n'.join(lines)

            # Формируем строку с данными ТТН
            ttn_date = ttn.date.strftime('%d.%m.%y') if ttn.date else timezone.now().strftime('%d.%m.%y')

            # Находим минимальную дату подачи среди цистерн этой ТТН
            entry_dates = [t.entry_date for t in tanks if t.entry_date]
            first_entry_date = min(entry_dates) if entry_dates else None
            entry_date_str = first_entry_date.strftime('%d.%m.%y') if first_entry_date else ""

            lines.append(
                f'{ttn.number};'
                f'{ttn_date};'
                f'{entry_date_str};'
                f'{ttn.shipper.name if ttn.shipper else ""};'
            )

            # Добавляем данные по КАЖДОЙ цистерне этой ТТН
            for tank in tanks:
                lines.append(
                    f'{tank.registration_number};'
                    f'{tank.gas_type if tank.gas_type != "Не выбран" else ttn.gas_type};'
                    f'{tank.netto_weight_ttn or 0:.3f};'
                    f'{tank.gas_weight or 0:.3f};'
                    f'{tank.departure_date.strftime("%d.%m.%y") if tank.departure_date else ""};'
                    f'{""};'  # Пустая накладная возврата
                )

        except RailwayTtn.DoesNotExist:
            logger.error(f'ТТН {ttn_number} не найдена!')
        except Exception as e:
            logger.error(f'Ошибка: {str(e)}')

        return '\n'.join(lines)

    def generate_loading_auto_gas_list(self, ttn_number):
        """Генерация данных для поставки газа автоцистерной (ГНС-ТТН2) по конкретной ТТН"""
        lines = ['ГНС-ТТН2']

        if not ttn_number:
            return '\n'.join(lines)

        try:
            # Получаем конкретную ТТН по номеру
            ttn = AutoTtn.objects.select_related('shipper', 'batch__truck').get(number=ttn_number)

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
        except AutoTtn.DoesNotExist:
            logger.error(f"ТТН {ttn_number} не найдена")
        except Exception as e:
            logger.error(f"Ошибка обработки ТТН {ttn_number}: {str(e)}")

        return '\n'.join(lines)

    def generate_unloading_auto_gas_list(self, ttn_number):
        """Генерация данных для отгрузки газа автоцистерной (ГНС-ТТН3) по конкретной ТТН"""
        lines = ['ГНС-ТТН3']

        if not ttn_number:
            return '\n'.join(lines)

        try:
            # Получаем конкретную ТТН по номеру
            ttn = AutoTtn.objects.select_related('consignee', 'batch__truck').get(number=ttn_number)

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
        except AutoTtn.DoesNotExist:
            logger.error(f"ТТН {ttn_number} не найдена")
        except Exception as e:
            logger.error(f"Ошибка обработки ТТН {ttn_number}: {str(e)}")

        return '\n'.join(lines)

    def generate_balloon_loading_list(self):
        batches = BalloonsLoadingBatch.objects.filter(begin_date=self.day_for_search)

        lines = ['ГНС-ТТН4']

        if batches:
            for batch in batches:
                try:
                    ttn = batch.ttn_loading.first()
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

    def generate_balloon_unloading_list(self):
        batches = BalloonsUnloadingBatch.objects.filter(begin_date=self.day_for_search)

        lines = ['ГНС-ТТН5']

        if batches:
            for batch in batches:
                try:
                    ttn = batch.ttn_unloading.first()
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
