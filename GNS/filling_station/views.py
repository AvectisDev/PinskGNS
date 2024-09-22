from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from django.views import generic

from .models import (Balloon, Truck, Trailer, RailwayTank, TTN, BalloonsLoadingBatch, BalloonsUnloadingBatch,
                     RailwayLoadingBatch, BalloonAmount, GasLoadingBatch, GasUnloadingBatch)
from .admin import BalloonResources
from .forms import (GetBalloonsAmount, BalloonForm, TruckForm, TrailerForm, RailwayTankForm, TTNForm,
                    BalloonsLoadingBatchForm, BalloonsUnloadingBatchForm, RailwayLoadingBatchForm, GasLoadingBatchForm,
                    GasUnloadingBatchForm)
from datetime import datetime, timedelta

STATUS_LIST = {
    '1': 'Регистрация пустого баллона на складе (из кассеты)',
    '2': 'Погрузка полного баллона в кассету',
    '3': 'Погрузка полного баллона на трал 1',
    '4': 'Погрузка полного баллона на трал 2',
    '5': 'Регистрация полного баллона на складе',
    '6': 'Регистрация пустого баллона на складе (рампа)',
    '7': 'Регистрация пустого баллона на складе (цех)',
    '8': 'Наполнение баллона сжиженным газом',
}


class BalloonListView(generic.ListView):
    model = Balloon
    paginate_by = 15

    def get_queryset(self):
        nfc_tag_filter = self.request.GET.get('nfc_tag', '')

        if nfc_tag_filter:
            return Balloon.objects.filter(nfc_tag=nfc_tag_filter)
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
    success_url = reverse_lazy("balloon_list")


def reader_info(request, reader='1'):
    current_date = datetime.now().date()
    previous_date = current_date - timedelta(days=1)

    if request.method == "POST":
        required_date = request.POST.get("date")
        format_required_date = datetime.strptime(required_date, '%Y-%m-%d')

        dataset = BalloonResources().export(Balloon.objects.filter(status=STATUS_LIST[reader], change_date=format_required_date))
        response = HttpResponse(dataset.xls, content_type='xls')
        response['Content-Disposition'] = f'attachment; filename="RFID_1_{required_date}.xls"'

        return response
    else:
        date_process = GetBalloonsAmount()

    balloons_list = Balloon.objects.order_by('-change_date', '-change_time').filter(status=STATUS_LIST[reader])
    current_quantity = BalloonAmount.objects.filter(reader_id=reader, change_date=current_date).first()
    previous_quantity = BalloonAmount.objects.filter(reader_id=reader, change_date=previous_date).first()

    paginator = Paginator(balloons_list, 15)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        "page_obj": page_obj,
        'current_quantity_by_reader': current_quantity.amount_of_rfid,
        'previous_quantity_by_reader': previous_quantity.amount_of_rfid,
        'current_quantity_by_sensor': current_quantity.amount_of_balloons,
        'previous_quantity_by_sensor': previous_quantity.amount_of_balloons,
        'form': date_process,
        'reader': reader
    }
    return render(request, "rfid_tables.html", context)


# Партии приёмки баллонов
class BalloonLoadingBatchListView(generic.ListView):
    model = BalloonsLoadingBatch
    paginate_by = 15
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
    success_url = reverse_lazy("filling_station:balloons_loading_batch")


# Партии отгрузки баллонов
class BalloonUnloadingBatchListView(generic.ListView):
    model = BalloonsUnloadingBatch
    paginate_by = 15
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
    success_url = reverse_lazy("filling_station:balloons_unloading_batch")


# Партии приёмки газа в автоцистернах
class GasLoadingBatchListView(generic.ListView):
    model = GasLoadingBatch
    paginate_by = 15
    template_name = 'filling_station/auto_batch_list.html'


class GasLoadingBatchDetailView(generic.DetailView):
    model = GasLoadingBatch
    context_object_name = 'batch'
    template_name = 'filling_station/auto_batch_detail.html'


class GasLoadingBatchUpdateView(generic.UpdateView):
    model = GasLoadingBatch
    form_class = GasLoadingBatchForm
    template_name = 'filling_station/_equipment_form.html'


class GasLoadingBatchDeleteView(generic.DeleteView):
    model = GasLoadingBatch
    success_url = reverse_lazy("filling_station:auto_gas_loading_batch")


# Партии отгрузки газа в автоцистернах
class GasUnloadingBatchListView(generic.ListView):
    model = GasUnloadingBatch
    paginate_by = 15
    template_name = 'filling_station/auto_batch_list.html'


class GasUnloadingBatchDetailView(generic.DetailView):
    model = GasUnloadingBatch
    context_object_name = 'batch'
    template_name = 'filling_station/auto_batch_detail.html'


class GasUnloadingBatchUpdateView(generic.UpdateView):
    model = GasUnloadingBatch
    form_class = GasUnloadingBatchForm
    template_name = 'filling_station/_equipment_form.html'


class GasUnloadingBatchDeleteView(generic.DeleteView):
    model = GasUnloadingBatch
    success_url = reverse_lazy("filling_station:auto_gas_unloading_batch")


# Партии приёмки газа в ж/д цистернах
class RailwayLoadingBatchListView(generic.ListView):
    model = RailwayLoadingBatch
    paginate_by = 15
    template_name = 'filling_station/railway_batch_list.html'


class RailwayLoadingBatchDetailView(generic.DetailView):
    model = RailwayLoadingBatch
    context_object_name = 'batch'
    template_name = 'filling_station/railway_batch_detail.html'


class RailwayLoadingBatchUpdateView(generic.UpdateView):
    model = RailwayLoadingBatch
    form_class = RailwayLoadingBatchForm
    template_name = 'filling_station/_equipment_form.html'


class RailwayLoadingBatchDeleteView(generic.DeleteView):
    model = RailwayLoadingBatch
    success_url = reverse_lazy("filling_station:railway_loading_batch")


# Грузовики
class TruckView(generic.ListView):
    model = Truck
    paginate_by = 15


class TruckDetailView(generic.DetailView):
    model = Truck
    paginate_by = 15


class TruckUpdateView(generic.UpdateView):
    model = Truck
    form_class = TruckForm
    template_name = 'filling_station/_equipment_form.html'


class TruckDeleteView(generic.DeleteView):
    model = Truck
    success_url = reverse_lazy("filling_station:truck_list")


# Прицепы
class TrailerView(generic.ListView):
    model = Trailer
    paginate_by = 15


class TrailerDetailView(generic.DetailView):
    model = Trailer
    paginate_by = 15


class TrailerUpdateView(generic.UpdateView):
    model = Trailer
    form_class = TrailerForm
    template_name = 'filling_station/_equipment_form.html'


class TrailerDeleteView(generic.DeleteView):
    model = Trailer
    success_url = reverse_lazy("filling_station:trailer_list")


# ж/д цистерны
class RailwayTankView(generic.ListView):
    model = RailwayTank
    paginate_by = 15


class RailwayTankDetailView(generic.DetailView):
    model = RailwayTank
    paginate_by = 15


class RailwayTankUpdateView(generic.UpdateView):
    model = RailwayTank
    form_class = RailwayTankForm
    template_name = 'filling_station/_equipment_form.html'


class RailwayTankDeleteView(generic.DeleteView):
    model = RailwayTank
    success_url = reverse_lazy("filling_station:railway_tank_list")


# ТТН
class TTNView(generic.ListView):
    model = TTN
    paginate_by = 15


class TTNDetailView(generic.DetailView):
    model = TTN
    paginate_by = 15


class TTNUpdateView(generic.UpdateView):
    model = TTN
    form_class = TTNForm
    template_name = 'filling_station/_equipment_form.html'


class TTNDeleteView(generic.DeleteView):
    model = TTN
    success_url = reverse_lazy("filling_station:ttn_list")
