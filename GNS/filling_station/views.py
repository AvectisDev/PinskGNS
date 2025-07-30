from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.urls import reverse_lazy, reverse
from django.views import generic
from django.db.models import Q, Sum
from railway_service.models import RailwayBatch
from .models import Balloon, Truck, Trailer, BalloonsLoadingBatch, BalloonsUnloadingBatch, BalloonAmount, Reader
from .admin import BalloonResources
from .forms import (
    GetBalloonsAmount,
    BalloonForm,
    TruckForm,
    TrailerForm,
    BalloonsLoadingBatchForm,
    BalloonsUnloadingBatchForm
)
from datetime import datetime, timedelta

STATUS_LIST = {
    1: 'Регистрация пустого баллона на складе (из кассеты)',
    2: 'Погрузка полного баллона в кассету',
    3: 'Погрузка полного баллона на трал 1',
    4: 'Погрузка полного баллона на трал 2',
    5: 'Регистрация полного баллона на складе',
    6: 'Регистрация пустого баллона на складе (рампа)',
    7: 'Регистрация пустого баллона на складе (цех)',
    8: 'Наполнение баллона сжиженным газом',
}


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


class BalloonUpdateView(generic.UpdateView):
    model = Balloon
    form_class = BalloonForm
    template_name = 'filling_station/_equipment_form.html'


class BalloonDeleteView(generic.DeleteView):
    model = Balloon
    success_url = reverse_lazy("filling_station:balloon_list")
    template_name = 'filling_station/balloon_confirm_delete.html'


def reader_info(request, reader=1):
    current_date = datetime.now().date()

    if request.method == "POST":
        form = GetBalloonsAmount(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
        else:
            start_date = current_date
            end_date = current_date

        action = request.POST.get('action')

        if action == 'export':
            dataset = BalloonResources().export(
                Reader.objects.filter(
                    number=reader,
                    change_date__range=(start_date, end_date)
                )
            )
            response = HttpResponse(dataset.xlsx, content_type='xlsx')
            response['Content-Disposition'] = f'attachment; filename="RFID_{reader}_{start_date}-{end_date}.xlsx"'
            return response

        elif action == 'show':
            # Показываем данные на странице
            pass

    else:
        form = GetBalloonsAmount()
        start_date = current_date
        end_date = current_date

    # Получаем общее количество баллонов для каждого ридера за период
    current_quantity = BalloonAmount.objects.filter(
        reader_id=reader,
        change_date__range=(start_date, end_date)
    ).aggregate(
        total_rfid=Sum('amount_of_rfid'),
        total_balloons=Sum('amount_of_balloons')
    )

    balloons_list = Reader.objects.order_by('-change_date', '-change_time').filter(number=reader)

    # Вычисляем количество баллонов в партиях по ТТН
    # Приёмка
    if reader == 6:
        loading_ttn_quantity = BalloonsLoadingBatch.objects.filter(
            reader_number=reader,
            begin_date__range=(start_date, end_date)
        ).aggregate(
            total_ttn=Sum('amount_of_ttn')
        )['total_ttn'] or 0
    else:
        loading_ttn_quantity = 0

    # Отгрузка
    if reader in [3,4]:
        unloading_ttn_quantity = BalloonsUnloadingBatch.objects.filter(
            reader_number=reader,
            begin_date__range=(start_date, end_date)
        ).aggregate(
            total_ttn=Sum('amount_of_ttn')
        )['total_ttn'] or 0
    else:
        unloading_ttn_quantity = 0

    paginator = Paginator(balloons_list, 10)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        "page_obj": page_obj,
        'current_quantity_by_reader': current_quantity['total_rfid'] or 0,
        'current_quantity_by_sensor': current_quantity['total_balloons'] or 0,
        'loading_ttn_quantity': loading_ttn_quantity,
        'unloading_ttn_quantity': unloading_ttn_quantity,
        'form': form,
        'reader': reader,
        'start_date': start_date,
        'end_date': end_date,
        'reader_status': STATUS_LIST[reader]
    }
    return render(request, 'filling_station/rfid_tables.html', context)


# Партии приёмки баллонов
class BalloonLoadingBatchListView(generic.ListView):
    model = BalloonsLoadingBatch
    paginate_by = 10
    template_name = 'filling_station/balloon_batch_list.html'


class BalloonLoadingBatchDetailView(generic.DetailView):
    model = BalloonsLoadingBatch
    context_object_name = 'batch'
    template_name = 'filling_station/balloon_batch_detail.html'


class BalloonLoadingBatchUpdateView(generic.UpdateView):
    model = BalloonsLoadingBatch
    form_class = BalloonsLoadingBatchForm
    template_name = 'filling_station/_equipment_form.html'


class BalloonLoadingBatchDeleteView(generic.DeleteView):
    model = BalloonsLoadingBatch
    success_url = reverse_lazy("filling_station:balloon_loading_batch_list")
    template_name = 'filling_station/balloons_loading_batch_confirm_delete.html'


# Партии отгрузки баллонов
class BalloonUnloadingBatchListView(generic.ListView):
    model = BalloonsUnloadingBatch
    paginate_by = 10
    template_name = 'filling_station/balloon_batch_list.html'


class BalloonUnloadingBatchDetailView(generic.DetailView):
    model = BalloonsUnloadingBatch
    context_object_name = 'batch'
    template_name = 'filling_station/balloon_batch_detail.html'


class BalloonUnloadingBatchUpdateView(generic.UpdateView):
    model = BalloonsUnloadingBatch
    form_class = BalloonsUnloadingBatchForm
    template_name = 'filling_station/_equipment_form.html'


class BalloonUnloadingBatchDeleteView(generic.DeleteView):
    model = BalloonsUnloadingBatch
    success_url = reverse_lazy("filling_station:balloon_unloading_batch_list")
    template_name = 'filling_station/balloons_unloading_batch_confirm_delete.html'


# Грузовики
class TruckView(generic.ListView):
    model = Truck
    paginate_by = 10


class TruckDetailView(generic.DetailView):
    model = Truck


class TruckCreateView(generic.CreateView):
    model = Truck
    form_class = TruckForm
    template_name = 'filling_station/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()


class TruckUpdateView(generic.UpdateView):
    model = Truck
    form_class = TruckForm
    template_name = 'filling_station/_equipment_form.html'


class TruckDeleteView(generic.DeleteView):
    model = Truck
    success_url = reverse_lazy("filling_station:truck_list")
    template_name = 'filling_station/truck_confirm_delete.html'


# Прицепы
class TrailerView(generic.ListView):
    model = Trailer
    paginate_by = 10


class TrailerDetailView(generic.DetailView):
    model = Trailer


class TrailerCreateView(generic.CreateView):
    model = Trailer
    form_class = TrailerForm
    template_name = 'filling_station/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()


class TrailerUpdateView(generic.UpdateView):
    model = Trailer
    form_class = TrailerForm
    template_name = 'filling_station/_equipment_form.html'


class TrailerDeleteView(generic.DeleteView):
    model = Trailer
    success_url = reverse_lazy("filling_station:trailer_list")
    template_name = 'filling_station/trailer_confirm_delete.html'


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
    else:
        form = GetBalloonsAmount()
        start_date = current_date
        end_date = current_date

    # Получаем общее количество баллонов для каждого ридера за период
    readers_data = {
        f'balloons_quantity_by_reader_{i}': BalloonAmount.objects.filter(
            reader_id=i,
            change_date__range=[start_date, end_date]
        ).aggregate(total=Sum('amount_of_rfid'))['total'] or 0
        for i in range(1, 9)
    }

    # Получаем статистику по партиям за период
    balloon_loading_stats = BalloonsLoadingBatch.get_period_stats(start_date, end_date)
    balloon_unloading_stats = BalloonsUnloadingBatch.get_period_stats(start_date, end_date)
    auto_gas_stats = AutoGasBatch.get_period_stats(start_date, end_date)
    railway_stats = RailwayBatch.get_period_stats(start_date, end_date)

    context = {
        **readers_data,
        'balloon_loading_stats': balloon_loading_stats,
        'balloon_unloading_stats': balloon_unloading_stats,
        'auto_gas_stats': auto_gas_stats,
        'railway_stats': railway_stats,
        'form': form,
        'start_date': start_date,
        'end_date': end_date,
    }

    return render(request, "statistic.html", context)
