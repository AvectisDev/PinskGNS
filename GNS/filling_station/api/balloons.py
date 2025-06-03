import logging
import requests
from ..models import Balloon, Reader, BalloonAmount, BalloonsLoadingBatch, BalloonsUnloadingBatch
from django.http import JsonResponse
from django.db.models import Sum, Count
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from rest_framework import generics, status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import api_view, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from datetime import datetime, date
from .serializers import (
    BalloonSerializer,
    BalloonAmountSerializer,
    BalloonsLoadingBatchSerializer,
    BalloonsUnloadingBatchSerializer,
    ActiveLoadingBatchSerializer,
    ActiveUnloadingBatchSerializer,
    BalloonAmountLoadingSerializer,
    BalloonAmountUnloadingSerializer
)

logger = logging.getLogger('filling_station')

USER_STATUS_LIST = [
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
    'Контрольное взвешивание'
]
BALLOONS_LOADING_READER_LIST = [1, 6]
BALLOONS_UNLOADING_READER_LIST = [2, 3, 4]


class BalloonViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

    @action(detail=False, methods=['get'], url_path='nfc/(?P<nfc_tag>[^/.]+)')
    def get_by_nfc(self, request, nfc_tag=None):
        balloon = get_object_or_404(Balloon, nfc_tag=nfc_tag)
        serializer = BalloonSerializer(balloon)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='serial-number/(?P<serial_number>[^/.]+)')
    def get_by_serial_number(self, request, serial_number=None):
        balloons = Balloon.objects.filter(serial_number=serial_number)
        serializer = BalloonSerializer(balloons, many=True)
        return Response(serializer.data)

    def get_balloon_by_nfc_tag(self, nfc_tag: str):
        """
        Метод для получения данных о баллоне по NFC-метке из Мириады.
        """
        # miriada server address
        BASE_URL = 'https://publicapi-vitebsk.cloud.gas.by'
        # метод получения основных данных баллона
        url = f'{BASE_URL}/getballoonbynfctag?nfctag={nfc_tag}&realm=brestoblgas'

        try:
            response = requests.get(url, timeout=3)
            response.raise_for_status()
            result = response.json()

            if result.get('status') == "Ok":
                self.logger.info(f"Паспорт баллона получен из Мириады. Номер метки: {nfc_tag}")
                return result['List']
            else:
                self.logger.warning(f"API Мириады вернуло ошибку. Номер метки: {nfc_tag}")
                return []

        except Exception as error:
            self.logger.error(f'Ошибка в методе получения паспорта баллона из Мириады: {error}')
            return None

    def send_status_to_miriada(self, send_type: str, nfc_tag: str, send_data: dict = None):
        """
        Метод для отправки статусов баллонов по NFC-метке в Мириаду.
        Поддерживается 3 основных типа отправки (send_type):
        filling - Наполнение баллона
        registering_in_warehouse - Регистрация баллона на склад
        loading_into_truck - Погрузка баллона в машину
        """
        send_urls = {
            'filling': f'{settings.MIRIADA_API_POST_URL}/fillingballoon',
            'registering_in_warehouse': f'{settings.MIRIADA_API_POST_URL}/balloontosklad',
            'loading_into_truck': f'{settings.MIRIADA_API_POST_URL}/balloontocar',
        }

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

        payload = {
            "nfctag": nfc_tag,
            "realm": "brestoblgas"
        }

        if send_data is not None:
            fulness = send_data.get('fulness')  # 1-полный, 0 — пустой
            if fulness:
                payload.update({"fulness": fulness})

            number_auto = send_data.get('number_auto')  # "AM 7881-2" номер машины.(Номер должен быть добавлен в  ПК «Автопарк»
            type_car = send_data.get('type_car')    # 0-кассета, 1 — трал
            if number_auto and type_car:
                payload.update({
                    "fulness": fulness,
                    "number_auto": number_auto,
                    "type_car": type_car
                })

        try:
            # Создаем запрос в Мириаду
            session = requests.Session()
            req = requests.Request(
                'POST',
                send_urls.get(send_type),
                auth=(settings.MIRIADA_AUTH_LOGIN, settings.MIRIADA_AUTH_PASSWORD),
                headers=headers,
                json=payload
            )
            prepared = session.prepare_request(req)

            # self.logger.debug(
            #     f"Подготовленный запрос:\n"
            #     f"URL: {prepared.url}\n"
            #     f"Headers: {prepared.headers}\n"
            #     f"Body: {prepared.body}"
            # )

            response = session.send(prepared, timeout=2)
            response.raise_for_status()
            if response.status_code == 200:
                self.logger.info(f"Статус по {send_type} успешно отправлен")
            else:
                self.logger.warning(f"Ошибка по {send_type}! Код: {response.status_code}, Описание: {response.reason}")

        except Exception as error:
            self.logger.error(f'Ошибка в методе отправки статуса баллона в Мириаду: {error}')

    @action(detail=False, methods=['post'], url_path='update-by-reader')
    def update_by_reader(self, request):
        """
        Метод для обновления данных баллона по NFC-метке. Если у баллона активен флаг "обновление паспорта", то
        повторно запрашиваем данные в Мириаде через метод get_balloon_by_nfc_tag
        """
        balloon_status = request.data.get('status')
        if not balloon_status:
            self.logger.error("Статус баллона отсутствует в теле запроса")

        nfc_tag = request.data.get('nfc_tag')
        if not nfc_tag:
            self.logger.error("Номер метки отсутствует в теле запроса")
            return Response({"error": "nfc_tag is required"}, status=400)

        balloon, created = Balloon.objects.update_or_create(
            nfc_tag=nfc_tag,
            defaults={
                'status': balloon_status
            }
        )
        reader_number = request.data.get('reader_number')
        if reader_number is None:
            self.logger.error("Номер ридера отсутствует в теле запроса")
        elif reader_number == 8:
            self.send_status_to_miriada(nfc_tag=nfc_tag, send_type='filling')
        elif reader_number == 6:
            self.send_status_to_miriada(nfc_tag=nfc_tag, send_type='registering_in_warehouse', send_data={'fulness':0})
        elif reader_number == 5:
            self.send_status_to_miriada(nfc_tag=nfc_tag, send_type='registering_in_warehouse', send_data={'fulness':1})
        elif reader_number in [3, 4]:
            self.send_status_to_miriada(nfc_tag=nfc_tag, send_type='loading_into_truck', send_data={'fulness':1, "type_car": 1, "number_auto": ' ',})
        elif reader_number == 2:
            self.send_status_to_miriada(nfc_tag=nfc_tag, send_type='loading_into_truck', send_data={'fulness':1, "type_car": 0, "number_auto": ' ',})

        # Если требуется обновление паспорта или идёт приёмка новых баллонов - выполняем запрос в Мириаду
        if balloon.update_passport_required in (True, None) or reader_number in [1, 6]:
            balloon_passport_from_miriada = self.get_balloon_by_nfc_tag(nfc_tag)
            # Данные получены
            if balloon_passport_from_miriada:
                balloon.update_passport_required = False
                balloon.serial_number = balloon_passport_from_miriada['number']
                balloon.netto = balloon_passport_from_miriada['netto']
                balloon.brutto = balloon_passport_from_miriada['brutto']
                balloon.filling_status = balloon_passport_from_miriada['status']
                balloon.save()

        reader_function = request.data.get('reader_function')
        if reader_function:
            self.add_balloon_to_batch_from_reader(balloon, reader_number, reader_function)

        # Добавляем информацию по баллону в таблицу с ридерами
        if reader_number:
            reader_balloon = Reader.objects.create(
                number=reader_number,
                nfc_tag=nfc_tag,
                serial_number=balloon.serial_number,
                size=balloon.size,
                netto=balloon.netto,
                brutto=balloon.brutto,
                filling_status=balloon.filling_status
            )
            # Сохраняем баллон в кэш на карусели наполнения
            if reader_number == 8:
                timeout_minutes = 10
                timeout_seconds = timeout_minutes * 60

                cache_key = f'reader_{reader_number}_balloon_stack'
                stack = cache.get(cache_key, [])
                # Добавляем объект в стек
                stack.insert(0, {
                    'number': reader_balloon.number,
                    'nfc_tag': reader_balloon.nfc_tag,
                    'serial_number': reader_balloon.serial_number,
                    'size': reader_balloon.size,
                    'netto': reader_balloon.netto,
                    'brutto': reader_balloon.brutto,
                    'filling_status': reader_balloon.filling_status,
                })
                logger.debug(f'Стек считывателя {reader_number} = {stack}')

                # Сохраняем обновленный стек в кэш
                cache.set(cache_key, stack, timeout=timeout_seconds)

        serializer = BalloonSerializer(balloon)
        return Response(serializer.data)

    def add_balloon_to_batch_from_reader(self, balloon, reader_number, batch_type):
        today = date.today()

        if batch_type == 'loading':
            batch = BalloonsLoadingBatch.objects.filter(begin_date=today,
                                                        reader_number=reader_number,
                                                        is_active=True).first()
        elif batch_type == 'unloading':
            batch = BalloonsUnloadingBatch.objects.filter(begin_date=today,
                                                          reader_number=reader_number,
                                                          is_active=True).first()
        else:
            batch = None

        if batch:
            batch.balloon_list.add(balloon)
            batch.amount_of_rfid = (batch.amount_of_rfid or 0) + 1
            batch.save()

    @action(detail=False, methods=['get'], url_path='statistic')
    def get_statistic(self, request):
        cache_key = 'get_balloon_statistic'
        cache_time = 600  # 10 минут
        data = cache.get(cache_key)

        if not data:
            today = date.today()
            first_day_of_month = today.replace(day=1)

            # Баллонов на станции
            filled_balloons_on_station = (Balloon.objects
                                          .filter(status='Регистрация полного баллона на складе')
                                          .aggregate(total=Count('nfc_tag')))
            empty_balloons_on_station = (Balloon.objects
                                         .filter(status__in=['Регистрация пустого баллона на складе (рампа)',
                                                             'Регистрация пустого баллона на складе (цех)'])
                                         .aggregate(total=Count('nfc_tag')))

            # Баллонов за текущий месяц
            balloons_monthly_stats = (BalloonAmount.objects
                                      .filter(change_date__gte=first_day_of_month)
                                      .order_by('reader_id')
                                      .values('reader_id')
                                      .annotate(balloons_month=Sum('amount_of_balloons'), rfid_month=Sum('amount_of_rfid'))
                                      )

            # Баллонов за текущий день
            balloons_today_stats = (BalloonAmount.objects
                                    .filter(change_date=today)
                                    .values('reader_id')
                                    .annotate(balloons_today=Sum('amount_of_balloons'), rfid_today=Sum('amount_of_rfid')))

            # Партий за текущий месяц
            loading_batches_last_month = (BalloonsLoadingBatch.objects
                                          .filter(begin_date__gte=first_day_of_month)
                                          .values('reader_number')
                                          .annotate(month_batches=Count('id'))
                                          )
            unloading_batches_last_month = (BalloonsUnloadingBatch.objects
                                            .filter(begin_date__gte=first_day_of_month)
                                            .values('reader_number')
                                            .annotate(month_batches=Count('id'))
                                            )
            # Объединяем результаты по партиям за последний месяц
            batches_last_month = {}
            for batch in loading_batches_last_month:
                reader_number = batch['reader_number']
                batches_last_month[reader_number] = batches_last_month.get(reader_number, 0) + batch['month_batches']

            for batch in unloading_batches_last_month:
                reader_number = batch['reader_number']
                batches_last_month[reader_number] = batches_last_month.get(reader_number, 0) + batch['month_batches']

            # Партий за текущий день
            loading_batches_last_day = (BalloonsLoadingBatch.objects
                                        .filter(begin_date=today)
                                        .values('reader_number')
                                        .annotate(day_batches=Count('id'))
                                        )
            unloading_batches_last_day = (BalloonsUnloadingBatch.objects
                                          .filter(begin_date=today)
                                          .values('reader_number')
                                          .annotate(day_batches=Count('id'))
                                          )
            # Объединяем результаты по партиям за последний день
            batches_last_day = {}
            for batch in loading_batches_last_day:
                reader_number = batch['reader_number']
                batches_last_day[reader_number] = batches_last_day.get(reader_number, 0) + batch['day_batches']

            for batch in unloading_batches_last_day:
                reader_number = batch['reader_number']
                batches_last_day[reader_number] = batches_last_day.get(reader_number, 0) + batch['day_batches']

            # Преобразуем данные по баллонам за сегодня в словарь для быстрого доступа
            today_dict = {stat['reader_id']: stat for stat in balloons_today_stats}

            # Объединяем данные
            response = []
            for stat in balloons_monthly_stats:
                reader_id = stat['reader_id']
                balloons_today = today_dict.get(reader_id, {}).get('balloons_today', 0)
                rfid_today = today_dict.get(reader_id, {}).get('rfid_today', 0)
                truck_month = batches_last_month.get(reader_id, 0)
                truck_today = batches_last_day.get(reader_id, 0)

                # Создаем новый словарь с данными
                response.append({
                    'reader_id': reader_id,
                    'balloons_month': stat['balloons_month'],
                    'rfid_month': stat['rfid_month'],
                    'balloons_today': balloons_today,
                    'rfid_today': rfid_today,
                    'truck_month': truck_month,
                    'truck_today': truck_today
                })

            response.append({
                'filled_balloons_on_station': filled_balloons_on_station.get('total', 0),
                'empty_balloons_on_station': empty_balloons_on_station.get('total', 0)
            })
            data = response
        cache.set(cache_key, data, cache_time)
        return JsonResponse(data, safe=False)

    def create(self, request):
        nfc_tag = request.data.get('nfc_tag', None)
        balloons = Balloon.objects.filter(nfc_tag=nfc_tag).exists()
        if not balloons:
            serializer = BalloonSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_409_CONFLICT)

    def partial_update(self, request, pk=None):
        balloon = get_object_or_404(Balloon, id=pk)

        serializer = BalloonSerializer(balloon, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@receiver(post_save, sender=Balloon)
@receiver(post_save, sender=BalloonAmount)
@receiver(post_save, sender=BalloonsLoadingBatch)
@receiver(post_save, sender=BalloonsUnloadingBatch)
@receiver(post_delete, sender=Balloon)
@receiver(post_delete, sender=BalloonAmount)
@receiver(post_delete, sender=BalloonsLoadingBatch)
@receiver(post_delete, sender=BalloonsUnloadingBatch)
def clear_cache(sender, **kwargs):
    cache.delete('get_balloon_statistic')


@api_view(['GET'])
def get_balloon_status_options(request):
    return Response(USER_STATUS_LIST)


@api_view(['GET'])
def get_loading_balloon_reader_list(request):
    return Response(BALLOONS_LOADING_READER_LIST)


@api_view(['GET'])
def get_unloading_balloon_reader_list(request):
    return Response(BALLOONS_UNLOADING_READER_LIST)


class BalloonsLoadingBatchViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='active')
    def is_active(self, request):
        batches = BalloonsLoadingBatch.objects.filter(is_active=True)
        serializer = ActiveLoadingBatchSerializer(batches, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='last-active')
    def last_active(self, request):
        batch = BalloonsLoadingBatch.objects.filter(is_active=True).first()
        if not batch:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = BalloonsLoadingBatchSerializer(batch)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='rfid-amount')
    def rfid_amount(self, request, pk=None):
        batch = get_object_or_404(BalloonsLoadingBatch, id=pk)
        serializer = BalloonAmountLoadingSerializer(batch)
        return Response(serializer.data)

    def create(self, request):
        serializer = BalloonsLoadingBatchSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk=None):
        batch = get_object_or_404(BalloonsLoadingBatch, id=pk)

        if not request.data.get('is_active', True):
            current_date = datetime.now()
            request.data['end_date'] = current_date.date()
            request.data['end_time'] = current_date.time()

        serializer = BalloonsLoadingBatchSerializer(batch, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path='add-balloon')
    def add_balloon(self, request, pk=None):
        nfc = request.data.get('nfc', None)
        batch = get_object_or_404(BalloonsLoadingBatch, id=pk)

        if nfc:
            balloon = get_object_or_404(Balloon, nfc_tag=nfc)
            if batch.balloon_list.filter(nfc_tag=nfc).exists():
                return Response(status=status.HTTP_409_CONFLICT)
            else:
                batch.balloon_list.add(balloon)
                batch.amount_of_rfid = (batch.amount_of_rfid or 0) + 1
                batch.save()
                return Response(status=status.HTTP_200_OK)

        return Response(status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path='remove-balloon')
    def remove_balloon(self, request, pk=None):
        nfc = request.data.get('nfc', None)
        batch = get_object_or_404(BalloonsLoadingBatch, id=pk)

        if nfc:
            balloon = get_object_or_404(Balloon, nfc_tag=nfc)
            if batch.balloon_list.filter(nfc_tag=nfc).exists():
                batch.balloon_list.remove(balloon)
                if batch.amount_of_rfid:
                    batch.amount_of_rfid -= 1
                else:
                    batch.amount_of_rfid = 0
                batch.save()
                return Response(status=status.HTTP_200_OK)
            else:
                return Response(status=status.HTTP_404_NOT_FOUND)

        return Response(status=status.HTTP_400_BAD_REQUEST)


class BalloonsUnloadingBatchViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='active')
    def is_active(self, request):
        batches = BalloonsUnloadingBatch.objects.filter(is_active=True)
        serializer = ActiveUnloadingBatchSerializer(batches, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='last-active')
    def last_active(self, request):
        batch = BalloonsUnloadingBatch.objects.filter(is_active=True).first()
        if not batch:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = BalloonsUnloadingBatchSerializer(batch)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='rfid-amount')
    def rfid_amount(self, request, pk=None):
        batch = get_object_or_404(BalloonsUnloadingBatch, id=pk)
        serializer = BalloonAmountUnloadingSerializer(batch)
        return Response(serializer.data)

    def create(self, request):
        serializer = BalloonsUnloadingBatchSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk=None):
        batch = get_object_or_404(BalloonsUnloadingBatch, id=pk)

        if not request.data.get('is_active', True):
            current_date = datetime.now()
            request.data['end_date'] = current_date.date()
            request.data['end_time'] = current_date.time()

        serializer = BalloonsUnloadingBatchSerializer(batch, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path='add-balloon')
    def add_balloon(self, request, pk=None):
        nfc = request.data.get('nfc', None)
        batch = get_object_or_404(BalloonsUnloadingBatch, id=pk)

        if nfc:
            balloon = get_object_or_404(Balloon, nfc_tag=nfc)
            if batch.balloon_list.filter(nfc_tag=nfc).exists():
                return Response(status=status.HTTP_409_CONFLICT)
            else:
                batch.balloon_list.add(balloon)
                batch.amount_of_rfid = (batch.amount_of_rfid or 0) + 1
                batch.save()
                return Response(status=status.HTTP_200_OK)

        return Response(status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path='remove-balloon')
    def remove_balloon(self, request, pk=None):
        nfc = request.data.get('nfc', None)
        batch = get_object_or_404(BalloonsUnloadingBatch, id=pk)

        if nfc:
            balloon = get_object_or_404(Balloon, nfc_tag=nfc)
            if batch.balloon_list.filter(nfc_tag=nfc).exists():
                batch.balloon_list.remove(balloon)
                if batch.amount_of_rfid:
                    batch.amount_of_rfid -= 1
                else:
                    batch.amount_of_rfid = 0
                batch.save()
                return Response(status=status.HTTP_200_OK)
            else:
                return Response(status=status.HTTP_404_NOT_FOUND)

        return Response(status=status.HTTP_400_BAD_REQUEST)


class BalloonAmountViewSet(viewsets.ViewSet):
    @action(detail=False, methods=['post'], url_path='update-amount-of-rfid')
    def update_amount_of_rfid(self, request, *args, **kwargs):
        today = date.today()
        reader_id = request.data.get('reader_id')

        instance, created = BalloonAmount.objects.get_or_create(
            change_date=today,
            reader_id=reader_id,
            defaults={
                'amount_of_rfid': 1,
                'amount_of_balloons': 0,
                'reader_status': request.data.get('reader_status')
            }
        )

        if not created:
            instance.amount_of_rfid += 1
            instance.save()

        return Response(status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='update-amount-of-sensor')
    def update_amount_of_sensor(self, request, *args, **kwargs):
        today = date.today()
        reader_id = request.data.get('reader_id')

        instance, created = BalloonAmount.objects.get_or_create(
            change_date=today,
            reader_id=reader_id,
            defaults={
                'amount_of_rfid': 0,
                'amount_of_balloons': 1,
                'reader_status': request.data.get('reader_status')
            }
        )

        if not created:
            instance.amount_of_balloons += 1
            instance.save()

        return Response(status=status.HTTP_200_OK)


@api_view(['GET'])
def get_active_balloon_batch(request):
    today = date.today()
    # Активные партии на сегодня
    loading_batches = (BalloonsLoadingBatch.objects
                       .filter(begin_date=today, is_active=True))
    unloading_batches = (BalloonsUnloadingBatch.objects
                         .filter(begin_date=today, is_active=True))

    response = []
    for batch in loading_batches:
        response.append({
            'reader_id': batch.reader_number,
            'truck_registration_number': batch.truck.registration_number,
            'trailer_registration_number': batch.trailer.registration_number
        })
    for batch in unloading_batches:
        response.append({
            'reader_id': batch.reader_number,
            'truck_registration_number': batch.truck.registration_number,
            'trailer_registration_number': batch.trailer.registration_number
        })
    return JsonResponse(response, safe=False)
