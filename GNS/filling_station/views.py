"""Представления веб-интерфейса АГНС: баллоны, партии, транспорт и статистика."""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from core.mixins import CancelFormMixin, ModalDeleteMixin, PreserveListQueryMixin
from core.navigation import redirect_preserve_query
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.urls import reverse_lazy, reverse
from django.views import generic
from django.views.decorators.http import require_POST
from django.db.models import Q, Sum, Count, OuterRef, Prefetch, Subquery
from ttn.models import MiriadaTtn
from autogas.models import AutoGasBatch
from railway_service.models import RailwayBatch
from .models import Balloon, Truck, Trailer, BalloonsBatch, BatchStatus, Reader, ReaderSettings, DailyReaderCounter
from .admin import BalloonResources
from .forms import (
    GetBalloonsAmount,
    BalloonForm,
    TruckForm,
    TrailerForm,
    BalloonsBatchForm
)
from .services import save_and_close_balloons_batch
from datetime import datetime, time, timedelta


BALLOON_STATUS_HISTORY_PAGE_SIZE = 10


class BalloonListView(generic.ListView):
    """Список баллонов с поиском по NFC-метке или заводскому номеру."""

    model = Balloon
    paginate_by = 10

    def get_queryset(self):
        """
        Возвращает queryset баллонов с опциональной фильтрацией по ``query``.

        Returns:
            QuerySet: Все баллоны либо отфильтрованные по NFC/серийному номеру.
        """
        query = self.request.GET.get('query', '')

        if query:
            return Balloon.objects.filter(
                Q(nfc_tag=query) | Q(serial_number=query)
            )
        else:
            return Balloon.objects.all()


class BalloonDetailView(generic.DetailView):
    """Карточка баллона с порцией истории статусов."""

    model = Balloon

    def get_context_data(self, **kwargs):
        """
        Дополняет контекст первой страницей истории статусов баллона.

        Args:
            **kwargs: Аргументы базового ``get_context_data``.

        Returns:
            dict: Контекст шаблона с полями ``status_history*``.
        """
        context = super().get_context_data(**kwargs)
        events_qs = (
            self.object.events
            .select_related('user')
            .order_by('-pgh_created_at', '-pgh_id')
        )
        total = events_qs.count()
        context['status_history'] = events_qs[:BALLOON_STATUS_HISTORY_PAGE_SIZE]
        context['status_history_total'] = total
        context['status_history_has_more'] = total > BALLOON_STATUS_HISTORY_PAGE_SIZE
        context['status_history_page_size'] = BALLOON_STATUS_HISTORY_PAGE_SIZE
        return context


def balloon_status_history(request, pk):
    """Partial HTML: следующая порция строк истории статусов баллона."""
    balloon = get_object_or_404(Balloon, pk=pk)
    try:
        offset = int(request.GET.get('offset', 0))
    except (TypeError, ValueError):
        offset = 0
    offset = max(offset, 0)

    events = (
        balloon.events
        .select_related('user')
        .order_by('-pgh_created_at', '-pgh_id')[offset:offset + BALLOON_STATUS_HISTORY_PAGE_SIZE]
    )
    return render(
        request,
        'filling_station/_balloon_status_history_rows.html',
        {'events': events},
    )


class BalloonUpdateView(PreserveListQueryMixin, generic.UpdateView):
    """Редактирование паспорта баллона."""

    model = Balloon
    form_class = BalloonForm
    template_name = 'filling_station/_equipment_form.html'

    def get_success_url(self):
        """
        URL карточки баллона после успешного сохранения.

        Returns:
            str: Абсолютный URL объекта.
        """
        return self.object.get_absolute_url()

    def post(self, request, *args, **kwargs):
        """
        Обрабатывает отправку формы; при ``cancel`` возвращает на карточку.

        Args:
            request: HTTP-запрос.
            *args: Позиционные аргументы CBV.
            **kwargs: Именованные аргументы CBV.

        Returns:
            HttpResponse: Редирект или ответ базового ``post``.
        """
        if 'cancel' in request.POST:
            return self.redirect_preserve_query('filling_station:balloon_detail', pk=self.get_object().pk)
        return super().post(request, *args, **kwargs)


class BalloonDeleteView(ModalDeleteMixin, PreserveListQueryMixin, generic.DeleteView):
    """Удаление баллона через модальное окно."""

    model = Balloon
    success_url = reverse_lazy("filling_station:balloon_list")


def reader_info(request, reader_number=1):
    """
    Страница статистики и журнала срабатываний RFID-ридера.

    Поддерживает фильтр по датам, пагинацию списка меток и экспорт в XLSX.

    Args:
        request: HTTP-запрос (GET — просмотр, POST ``action=export`` — выгрузка).
        reader_number (int): Номер ридера из URL.

    Returns:
        HttpResponse: HTML-страница или файл Excel при экспорте.
    """
    current_date = datetime.now().date()

    if request.method == 'POST' and request.POST.get('action') == 'export':
        form = GetBalloonsAmount(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            dataset = BalloonResources().export(
                Reader.objects.filter(
                    number__number=reader_number,
                    nfc_tag__isnull=False,
                    change_date__date__gte=start_date,
                    change_date__date__lte=end_date,
                )
            )
            response = HttpResponse(dataset.xlsx, content_type='xlsx')
            response['Content-Disposition'] = (
                f'attachment; filename="RFID_{reader_number}_{start_date}-{end_date}.xlsx"'
            )
            return response

    form = GetBalloonsAmount(request.GET or None)
    if form.is_valid():
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
    else:
        start_date = end_date = current_date
        form = GetBalloonsAmount(initial={
            'start_date': start_date,
            'end_date': end_date,
        })

    # Получаем статистику из DailyReaderCounter
    reader = ReaderSettings.objects.get(number=reader_number)
    counter_stats = DailyReaderCounter.get_reader_period_stats(reader, start_date, end_date)
    
    # Получаем список баллонов из Reader для отображения в таблице
    # (только баллоны с RFID метками)
    balloons_list = Reader.objects.filter(
        number=reader_number,
        change_date__date__gte=start_date,
        change_date__date__lte=end_date,
        nfc_tag__isnull=False
    ).select_related('number').order_by('-change_date')

    paginator = Paginator(balloons_list, 10)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        "page_obj": page_obj,
        'current_quantity_by_reader': counter_stats['total_rfid'],
        'current_quantity_by_sensor': counter_stats['total_sensor'],
        'form': form,
        'reader': reader,
        'start_date': start_date,
        'end_date': end_date
    }
    return render(request, 'filling_station/rfid_tables.html', context)


class BalloonBatchTypeMixin:
    """Определяет тип партии (приёмка/отгрузка) по URL."""

    def get_batch_type(self):
        """
        Извлекает тип партии из пути запроса.

        Returns:
            str | None: ``'u'`` (приёмка), ``'l'`` (отгрузка) или ``None``.
        """
        path = self.request.path.lower()
        if 'unloading' in path:
            return 'u'
        if 'loading' in path:
            return 'l'
        return None


# Единые классы для работы с партиями баллонов
class BalloonBatchListView(BalloonBatchTypeMixin, generic.ListView):
    """Отображает список партий баллонов в зависимости от типа"""
    model = BalloonsBatch
    form_class = BalloonsBatchForm
    paginate_by = 10
    template_name = 'filling_station/balloon_batch_list.html'

    def get_queryset(self):
        """
        Список партий с ТТН, отфильтрованный по типу из URL.

        Returns:
            QuerySet: Партии приёмки, отгрузки или все.
        """
        batch_type = self.get_batch_type()
        ttn_name_sq = MiriadaTtn.objects.filter(
            ttn_id=OuterRef('ttn_id')
        ).values('name')[:1]
        queryset = BalloonsBatch.objects.select_related(
            'truck', 'trailer', 'truck__type'
        ).annotate(ttn_name=Subquery(ttn_name_sq))
        if batch_type:
            return queryset.filter(batch_type=batch_type)
        return queryset.all()


class BalloonBatchDetailView(BalloonBatchTypeMixin, generic.DetailView):
    """Отображает детальное представление партии баллонов"""
    model = BalloonsBatch
    context_object_name = 'batch'
    template_name = 'filling_station/balloon_batch_detail.html'

    def get_queryset(self):
        """
        Queryset партии с предзагрузкой баллонов и именем ТТН.

        Returns:
            QuerySet: Оптимизированный queryset с фильтром по типу партии.
        """
        ttn_name_sq = MiriadaTtn.objects.filter(
            ttn_id=OuterRef('ttn_id')
        ).values('name')[:1]
        queryset = BalloonsBatch.objects.select_related(
            'truck', 'trailer', 'truck__type'
        ).prefetch_related(
            Prefetch('balloon_list', queryset=Balloon.objects.order_by('nfc_tag'))
        ).annotate(ttn_name=Subquery(ttn_name_sq))
        batch_type = self.get_batch_type()
        if batch_type:
            queryset = queryset.filter(batch_type=batch_type)
        return queryset


class BalloonBatchUpdateView(BalloonBatchTypeMixin, PreserveListQueryMixin, generic.UpdateView):
    """Универсальное редактирование партии баллонов"""
    model = BalloonsBatch
    form_class = BalloonsBatchForm
    template_name = 'filling_station/_equipment_form.html'

    def get_queryset(self):
        """
        Queryset партий с транспортом, ограниченный типом из URL.

        Returns:
            QuerySet: Партии для редактирования.
        """
        queryset = BalloonsBatch.objects.select_related('truck', 'trailer', 'truck__type')
        batch_type = self.get_batch_type()
        if batch_type:
            queryset = queryset.filter(batch_type=batch_type)
        return queryset

    def get_success_url(self):
        """
        URL карточки партии после сохранения.

        Returns:
            str: Абсолютный URL объекта.
        """
        return self.object.get_absolute_url()

    def post(self, request, *args, **kwargs):
        """
        Обрабатывает форму; при ``cancel`` возвращает на карточку партии.

        Args:
            request: HTTP-запрос.
            *args: Позиционные аргументы CBV.
            **kwargs: Именованные аргументы CBV.

        Returns:
            HttpResponse: Редирект или ответ базового ``post``.
        """
        if 'cancel' in request.POST:
            return redirect_preserve_query(request, self.get_object().get_absolute_url())
        return super().post(request, *args, **kwargs)


#@login_required
@require_POST
def balloon_batch_retry_close(request, pk):
    """Завершить партию: сохранить текущие данные и закрыть ТТН в Мириаде."""
    path = request.path.lower()
    batch_type = 'u' if 'unloading' in path else 'l'
    batch = get_object_or_404(BalloonsBatch, pk=pk, batch_type=batch_type)

    # Разрешаем повтор, только если есть флаг ошибки Мириады
    if batch.status != BatchStatus.MIRIADA_ERROR:
        messages.error(request, 'Партия не содержит ошибок.')
        return redirect_preserve_query(request, batch.get_absolute_url())

    success, error_payload, _ = save_and_close_balloons_batch(batch, request.POST)
    if success:
        messages.success(request, f'Партия №{batch.id} успешно завершена. ТТН закрыта в Мириаде.')
    elif isinstance(error_payload, dict) and error_payload.get('message'):
        messages.error(request, error_payload['message'])
    elif error_payload:
        messages.error(request, error_payload)

    return redirect_preserve_query(request, batch.get_absolute_url())


class BalloonBatchDeleteView(BalloonBatchTypeMixin, ModalDeleteMixin, PreserveListQueryMixin, generic.DeleteView):
    """Универсальное удаление партии баллонов"""
    model = BalloonsBatch

    def get_queryset(self):
        """
        Queryset партий для удаления с фильтром по типу из URL.

        Returns:
            QuerySet: Партии приёмки или отгрузки.
        """
        queryset = BalloonsBatch.objects.select_related('truck', 'trailer', 'truck__type')
        batch_type = self.get_batch_type()
        if batch_type:
            queryset = queryset.filter(batch_type=batch_type)
        return queryset

    def get_success_url(self):
        """
        Список партий того же типа после удаления.

        Returns:
            str: URL списка приёмки или отгрузки.
        """
        if self.get_batch_type() == 'u':
            return reverse_lazy("filling_station:balloon_unloading_batch_list")
        return reverse_lazy("filling_station:balloon_loading_batch_list")


# Алиасы для обратной совместимости
BalloonLoadingBatchListView = BalloonBatchListView
BalloonLoadingBatchDetailView = BalloonBatchDetailView
BalloonLoadingBatchUpdateView = BalloonBatchUpdateView
BalloonLoadingBatchDeleteView = BalloonBatchDeleteView

BalloonUnloadingBatchListView = BalloonBatchListView
BalloonUnloadingBatchDetailView = BalloonBatchDetailView
BalloonUnloadingBatchUpdateView = BalloonBatchUpdateView
BalloonUnloadingBatchDeleteView = BalloonBatchDeleteView


# Грузовики
class TruckView(generic.ListView):
    """Список тягачей с поиском по госномеру или марке."""

    model = Truck
    paginate_by = 10

    def get_queryset(self):
        """
        Queryset тягачей с опциональным поиском по ``query``.

        Returns:
            QuerySet: Тягачи с ``select_related('type')``.
        """
        queryset = super().get_queryset().select_related('type')
        query = self.request.GET.get('query', '').strip()
        if query:
            queryset = queryset.filter(
                Q(registration_number__icontains=query) | Q(car_brand__icontains=query)
            )
        return queryset


class TruckDetailView(generic.DetailView):
    """Карточка тягача."""

    model = Truck


class TruckCreateView(CancelFormMixin, PreserveListQueryMixin, generic.CreateView):
    """Создание записи тягача."""

    model = Truck
    form_class = TruckForm
    template_name = 'filling_station/_equipment_form.html'
    cancel_url = reverse_lazy('filling_station:truck_list')

    def get_success_url(self):
        """
        URL карточки созданного тягача.

        Returns:
            str: Абсолютный URL объекта.
        """
        return self.object.get_absolute_url()


class TruckUpdateView(PreserveListQueryMixin, generic.UpdateView):
    """Редактирование тягача."""

    model = Truck
    form_class = TruckForm
    template_name = 'filling_station/_equipment_form.html'

    def get_success_url(self):
        """
        URL карточки тягача после сохранения.

        Returns:
            str: Абсолютный URL объекта.
        """
        return self.object.get_absolute_url()

    def post(self, request, *args, **kwargs):
        """
        Обрабатывает форму; при ``cancel`` возвращает на карточку тягача.

        Args:
            request: HTTP-запрос.
            *args: Позиционные аргументы CBV.
            **kwargs: Именованные аргументы CBV.

        Returns:
            HttpResponse: Редирект или ответ базового ``post``.
        """
        if 'cancel' in request.POST:
            return self.redirect_preserve_query('filling_station:truck_detail', pk=self.get_object().pk)
        return super().post(request, *args, **kwargs)


class TruckDeleteView(ModalDeleteMixin, PreserveListQueryMixin, generic.DeleteView):
    """Удаление тягача через модальное окно."""

    model = Truck
    success_url = reverse_lazy("filling_station:truck_list")


# Прицепы
class TrailerView(generic.ListView):
    """Список прицепов с поиском по госномеру или марке."""

    model = Trailer
    paginate_by = 10

    def get_queryset(self):
        """
        Queryset прицепов с опциональным поиском по ``query``.

        Returns:
            QuerySet: Прицепы с ``select_related('type', 'truck')``.
        """
        queryset = super().get_queryset().select_related('type', 'truck')
        query = self.request.GET.get('query', '').strip()
        if query:
            queryset = queryset.filter(
                Q(registration_number__icontains=query) | Q(trailer_brand__icontains=query)
            )
        return queryset


class TrailerDetailView(generic.DetailView):
    """Карточка прицепа."""

    model = Trailer


class TrailerCreateView(CancelFormMixin, PreserveListQueryMixin, generic.CreateView):
    """Создание записи прицепа."""

    model = Trailer
    form_class = TrailerForm
    template_name = 'filling_station/_equipment_form.html'
    cancel_url = reverse_lazy('filling_station:trailer_list')

    def get_success_url(self):
        """
        URL карточки созданного прицепа.

        Returns:
            str: Абсолютный URL объекта.
        """
        return self.object.get_absolute_url()


class TrailerUpdateView(PreserveListQueryMixin, generic.UpdateView):
    """Редактирование прицепа."""

    model = Trailer
    form_class = TrailerForm
    template_name = 'filling_station/_equipment_form.html'

    def get_success_url(self):
        """
        URL карточки прицепа после сохранения.

        Returns:
            str: Абсолютный URL объекта.
        """
        return self.object.get_absolute_url()

    def post(self, request, *args, **kwargs):
        """
        Обрабатывает форму; при ``cancel`` возвращает на карточку прицепа.

        Args:
            request: HTTP-запрос.
            *args: Позиционные аргументы CBV.
            **kwargs: Именованные аргументы CBV.

        Returns:
            HttpResponse: Редирект или ответ базового ``post``.
        """
        if 'cancel' in request.POST:
            return self.redirect_preserve_query('filling_station:trailer_detail', pk=self.get_object().pk)
        return super().post(request, *args, **kwargs)


class TrailerDeleteView(ModalDeleteMixin, PreserveListQueryMixin, generic.DeleteView):
    """Удаление прицепа через модальное окно."""

    model = Trailer
    success_url = reverse_lazy("filling_station:trailer_list")


# Обработка данных для вкладки "Статистика"
def statistic(request):
    """
    Сводная статистика АГНС за выбранный период.

    Args:
        request: HTTP-запрос с формой дат (GET/POST).

    Returns:
        HttpResponse: Страница ``statistic.html`` с агрегатами по ридерам и партиям.
    """
    current_date = datetime.now().date()

    if request.method == "POST":
        form = GetBalloonsAmount(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
        else:
            start_date = current_date
            end_date = current_date
            form = GetBalloonsAmount(initial={
                'start_date': start_date,
                'end_date': end_date,
            })
    else:
        start_date = current_date
        end_date = current_date
        form = GetBalloonsAmount(initial={
            'start_date': start_date,
            'end_date': end_date,
        })

    context = {
        'readers_stats': Reader.get_all_readers_stats(start_date, end_date),
        'balloon_loading_stats': BalloonsBatch.get_period_stats(
            start_date, end_date, batch_type='l'
        ),
        'balloon_unloading_stats': BalloonsBatch.get_period_stats(
            start_date, end_date, batch_type='u'
        ),
        'auto_gas_stats': AutoGasBatch.get_period_stats(start_date, end_date),
        'railway_stats': RailwayBatch.get_period_stats(start_date, end_date),
        'form': form,
        'start_date': start_date,
        'end_date': end_date,
    }

    return render(request, "statistic.html", context)
