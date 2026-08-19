from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from core.mixins import ModalDeleteMixin, PreserveListQueryMixin
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
from .models import Balloon, Truck, Trailer, BalloonsBatch, Reader, ReaderSettings, DailyReaderCounter
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


class BalloonListView(generic.ListView):
    model = Balloon
    paginate_by = 10

    def get_queryset(self):
        query = self.request.GET.get('query', '')

        if query:
            return Balloon.objects.filter(
                Q(nfc_tag=query) | Q(serial_number=query)
            )
        else:
            return Balloon.objects.all()


class BalloonDetailView(generic.DetailView):
    model = Balloon


class BalloonUpdateView(PreserveListQueryMixin, generic.UpdateView):
    model = Balloon
    form_class = BalloonForm
    template_name = 'filling_station/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def post(self, request, *args, **kwargs):
        if 'cancel' in request.POST:
            return self.redirect_preserve_query('filling_station:balloon_detail', pk=self.get_object().pk)
        return super().post(request, *args, **kwargs)


class BalloonDeleteView(ModalDeleteMixin, PreserveListQueryMixin, generic.DeleteView):
    model = Balloon
    success_url = reverse_lazy("filling_station:balloon_list")


def reader_info(request, reader_number=1):
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
        queryset = BalloonsBatch.objects.select_related('truck', 'trailer', 'truck__type')
        batch_type = self.get_batch_type()
        if batch_type:
            queryset = queryset.filter(batch_type=batch_type)
        return queryset

    def get_success_url(self):
        return self.object.get_absolute_url()

    def post(self, request, *args, **kwargs):
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
    if not batch.miriada_close_failed:
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
        queryset = BalloonsBatch.objects.select_related('truck', 'trailer', 'truck__type')
        batch_type = self.get_batch_type()
        if batch_type:
            queryset = queryset.filter(batch_type=batch_type)
        return queryset

    def get_success_url(self):
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
    model = Truck
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('type')
        query = self.request.GET.get('query', '').strip()
        if query:
            queryset = queryset.filter(
                Q(registration_number__icontains=query) | Q(car_brand__icontains=query)
            )
        return queryset


class TruckDetailView(generic.DetailView):
    model = Truck


class TruckCreateView(PreserveListQueryMixin, generic.CreateView):
    model = Truck
    form_class = TruckForm
    template_name = 'filling_station/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()


class TruckUpdateView(PreserveListQueryMixin, generic.UpdateView):
    model = Truck
    form_class = TruckForm
    template_name = 'filling_station/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def post(self, request, *args, **kwargs):
        if 'cancel' in request.POST:
            return self.redirect_preserve_query('filling_station:truck_detail', pk=self.get_object().pk)
        return super().post(request, *args, **kwargs)


class TruckDeleteView(ModalDeleteMixin, PreserveListQueryMixin, generic.DeleteView):
    model = Truck
    success_url = reverse_lazy("filling_station:truck_list")


# Прицепы
class TrailerView(generic.ListView):
    model = Trailer
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('type', 'truck')
        query = self.request.GET.get('query', '').strip()
        if query:
            queryset = queryset.filter(
                Q(registration_number__icontains=query) | Q(trailer_brand__icontains=query)
            )
        return queryset


class TrailerDetailView(generic.DetailView):
    model = Trailer


class TrailerCreateView(PreserveListQueryMixin, generic.CreateView):
    model = Trailer
    form_class = TrailerForm
    template_name = 'filling_station/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()


class TrailerUpdateView(PreserveListQueryMixin, generic.UpdateView):
    model = Trailer
    form_class = TrailerForm
    template_name = 'filling_station/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def post(self, request, *args, **kwargs):
        if 'cancel' in request.POST:
            return self.redirect_preserve_query('filling_station:trailer_detail', pk=self.get_object().pk)
        return super().post(request, *args, **kwargs)


class TrailerDeleteView(ModalDeleteMixin, PreserveListQueryMixin, generic.DeleteView):
    model = Trailer
    success_url = reverse_lazy("filling_station:trailer_list")


# Обработка данных для вкладки "Статистика"
def statistic(request):
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
