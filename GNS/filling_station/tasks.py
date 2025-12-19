import logging
from celery import shared_task
from . import services

logger = logging.getLogger('filling_station')


@shared_task(bind=True, max_retries=3)
def process_rfid_balloon_data(self, nfc_tag, reader_number):
    """
    Celery задача для обработки данных баллона от RFID ридера.

    Args:
        nfc_tag (str): NFC метка баллона (может быть None)
        reader_number (int): Номер ридера

    Returns:
        dict: Результат обработки
    """
    try:
        logger.info(f'Обработка RFID данных: nfc_tag={nfc_tag}, reader_number={reader_number}')

        if nfc_tag is None:
            # Обработка сигнала без NFC (оптический датчик)
            reader = services.processing_request_without_nfc(reader_number)
            if reader:
                return {'status': 'success', 'message': 'Баллон без NFC обработан', 'reader': reader.number}
            else:
                return {'status': 'error', 'message': 'Ошибка обработки баллона без NFC'}

        else:
            # Обработка сигнала с NFC меткой
            result = services.processing_request_with_nfc(nfc_tag=nfc_tag, reader_number=reader_number)
            if result:
                balloon, reader = result

                # Отправка статусов в Мириаду (только для определенных ридеров)
                if (2 <= reader.number <= 6) or reader.number == 8:
                    send_status_to_miriada_task.delay(reader.number, balloon.nfc_tag)

                return {
                    'status': 'success',
                    'message': f'Баллон {balloon.nfc_tag} обработан',
                    'balloon_nfc': balloon.nfc_tag,
                    'reader_number': reader.number,
                    'filling_status': balloon.filling_status
                }
            else:
                return {'status': 'error', 'message': f'Ошибка обработки баллона {nfc_tag}'}

    except Exception as exc:
        logger.error(f'Ошибка в задаче process_rfid_balloon_data: {exc}')
        # Повторяем задачу при ошибке
        raise self.retry(exc=exc, countdown=5)


@shared_task(bind=True)
def send_status_to_miriada_task(self, reader_number, nfc_tag):
    """
    Celery задача для отправки статуса в систему Мириада.

    Args:
        reader_number (int): Номер ридера
        nfc_tag (str): NFC метка баллона
    """
    try:
        logger.info(f'Отправка статуса в Мириаду: reader={reader_number}, nfc_tag={nfc_tag}')
        success = services.send_status_to_miriada(reader_number, nfc_tag)
        if success:
            logger.info(f'Статус успешно отправлен в Мириаду для {nfc_tag}')
        else:
            logger.warning(f'Не удалось отправить статус в Мириаду для {nfc_tag}')
    except Exception as exc:
        logger.error(f'Ошибка при отправке статуса в Мириаду: {exc}')
