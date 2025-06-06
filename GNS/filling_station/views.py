from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.urls import reverse_lazy, reverse
from django.views import generic
from django.db.models import Q, Sum
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import (Balloon, Truck, Trailer, RailwayTank, TTN, BalloonsLoadingBatch, BalloonsUnloadingBatch, NewTTN,
                     RailwayBatch, BalloonAmount, AutoGasBatch, Reader, RailwayTtn, AutoTtn,
                     AutoGasBatchSettings)
from .admin import BalloonResources
from .forms import (GetBalloonsAmount, BalloonForm, TruckForm, TrailerForm, RailwayTankForm, TTNForm, AutoTtnForm,
                    BalloonsLoadingBatchForm, BalloonsUnloadingBatchForm, RailwayBatchForm, AutoGasBatchForm,
                    RailwayTtnForm)
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
            # Экспортируем данные в Excel
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

    current_quantity_rfid = current_quantity['total_rfid'] or 0
    current_quantity_balloons = current_quantity['total_balloons'] or 0

    paginator = Paginator(balloons_list, 10)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        "page_obj": page_obj,
        'current_quantity_by_reader': current_quantity_rfid,
        'current_quantity_by_sensor': current_quantity_balloons,
        'form': form,
        'reader': reader,
        'start_date': start_date,
        'end_date': end_date,
        'reader_status': STATUS_LIST[reader]
    }
    return render(request, "rfid_tables.html", context)


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


# Партии автоцистерн
class AutoGasBatchListView(generic.ListView):
    model = AutoGasBatch
    paginate_by = 10
    template_name = 'filling_station/auto_batch_list.html'


class AutoGasBatchDetailView(generic.DetailView):
    model = AutoGasBatch
    context_object_name = 'batch'
    template_name = 'filling_station/auto_batch_detail.html'


class AutoGasBatchUpdateView(generic.UpdateView):
    model = AutoGasBatch
    form_class = AutoGasBatchForm
    template_name = 'filling_station/_equipment_form.html'


class AutoGasBatchDeleteView(generic.DeleteView):
    model = AutoGasBatch
    success_url = reverse_lazy("filling_station:auto_gas_batch_list")
    template_name = 'filling_station/auto_batch_confirm_delete.html'


# Партии приёмки газа в ж/д цистернах
class RailwayBatchListView(generic.ListView):
    model = RailwayBatch
    paginate_by = 10
    template_name = 'filling_station/railway_batch_list.html'


class RailwayBatchDetailView(generic.DetailView):
    model = RailwayBatch
    queryset = RailwayBatch.objects.prefetch_related('railway_tank_list')
    context_object_name = 'batch'
    template_name = 'filling_station/railway_batch_detail.html'


class RailwayBatchUpdateView(generic.UpdateView):
    model = RailwayBatch
    form_class = RailwayBatchForm
    template_name = 'filling_station/_equipment_form.html'


class RailwayBatchDeleteView(generic.DeleteView):
    model = RailwayBatch
    success_url = reverse_lazy("filling_station:railway_batch_list")
    template_name = 'filling_station/railway_batch_confirm_delete.html'


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


# ж/д цистерны
class RailwayTankView(generic.ListView):
    model = RailwayTank
    paginate_by = 10


class RailwayTankDetailView(generic.DetailView):
    model = RailwayTank


class RailwayTankCreateView(generic.CreateView):
    model = RailwayTank
    form_class = RailwayTankForm
    template_name = 'filling_station/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()


class RailwayTankUpdateView(generic.UpdateView):
    model = RailwayTank
    form_class = RailwayTankForm
    template_name = 'filling_station/_equipment_form.html'


class RailwayTankDeleteView(generic.DeleteView):
    model = RailwayTank
    success_url = reverse_lazy("filling_station:railway_tank_list")
    template_name = 'filling_station/railway_tank_confirm_delete.html'


# ТТН для баллонов
class TTNView(generic.ListView):
    model = NewTTN
    paginate_by = 10


class TTNDetailView(generic.DetailView):
    model = NewTTN


class TTNCreateView(generic.CreateView):
    model = NewTTN
    form_class = TTNForm
    template_name = 'filling_station/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'ТТН {self.object.number} успешно создана')
        return response


class TTNUpdateView(generic.UpdateView):
    model = NewTTN
    form_class = TTNForm
    template_name = 'filling_station/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'ТТН {self.object.number} успешно обновлена')
        return response


class TTNDeleteView(generic.DeleteView):
    model = NewTTN
    success_url = reverse_lazy("filling_station:ttn_list")
    template_name = 'filling_station/newttn_confirm_delete.html'


# ТТН для жд цистерн
class RailwayTtnView(generic.ListView):
    model = RailwayTtn
    paginate_by = 10


class RailwayTtnDetailView(generic.DetailView):
    model = RailwayTtn


class RailwayTtnCreateView(generic.CreateView):
    model = RailwayTtn
    form_class = RailwayTtnForm
    template_name = 'filling_station/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        self.object = form.save(commit=False)
        railway_ttn_number = form.cleaned_data['railway_ttn']

        # Находим все цистерны с этим номером накладной и суммируем значения
        tanks = RailwayTank.objects.filter(railway_ttn=railway_ttn_number)
        self.object.total_gas_amount_by_scales = tanks.aggregate(total=Sum('gas_weight'))['total'] or 0
        self.object.total_gas_amount_by_ttn = tanks.aggregate(total=Sum('netto_weight_ttn'))['total'] or 0
        self.object.save()

        # Добавляем цистерны в ManyToMany связь
        self.object.railway_tank_list.set(tanks)

        messages.success(self.request, f'ТТН {self.object.number} успешно создана')
        return super().form_valid(form)


class RailwayTtnUpdateView(generic.UpdateView):
    model = RailwayTtn
    form_class = RailwayTtnForm
    template_name = 'filling_station/_equipment_form.html'

    def form_valid(self, form):
        new_railway_ttn = form.cleaned_data['railway_ttn']

        self.object = form.save(commit=False)

        # Обновляем суммы
        tanks = RailwayTank.objects.filter(railway_ttn=new_railway_ttn)
        self.object.total_gas_amount_by_scales = tanks.aggregate(total=Sum('gas_weight'))['total'] or 0
        self.object.total_gas_amount_by_ttn = tanks.aggregate(total=Sum('netto_weight_ttn'))['total'] or 0

        # Обновляем ManyToMany связь
        self.object.railway_tank_list.set(tanks)

        self.object.save()
        return super().form_valid(form)


class RailwayTtnDeleteView(generic.DeleteView):
    model = RailwayTtn
    success_url = reverse_lazy("filling_station:railway_ttn_list")
    template_name = 'filling_station/railwayttn_confirm_delete.html'


# ТТН для автоцистерн
@require_POST
# @login_required
def update_weight_source(request):
    weight_source = request.POST.get('weight_source', 's')  # 'f' если чекбокс отмечен, иначе 's'
    settings, _ = AutoGasBatchSettings.objects.get_or_create()
    settings.weight_source = weight_source
    settings.save()
    return redirect('filling_station:auto_ttn_list')


class AutoTtnView(generic.ListView):
    model = AutoTtn
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        settings = AutoGasBatchSettings.objects.first()
        context['weight_source'] = settings.weight_source if settings else 'f'
        return context


class AutoTtnDetailView(generic.DetailView):
    model = AutoTtn


class AutoTtnCreateView(generic.CreateView):
    model = AutoTtn
    form_class = AutoTtnForm
    template_name = 'filling_station/_equipment_form.html'

    def form_valid(self, form):
        response = super().form_valid(form)

        self.update_ttn_values()

        return response

    def get_success_url(self):
        return self.object.get_absolute_url()

    def update_ttn_values(self):
        batch = self.object.batch
        if batch:
            settings = AutoGasBatchSettings.objects.first()

            # Определяем источник данных и значение количества газа
            if settings and settings.weight_source == 'f':
                gas_amount = batch.gas_amount
                source = 'Расходомер'
            else:
                gas_amount = batch.weight_gas_amount
                source = 'Весы'

            self.object.total_gas_amount = gas_amount
            self.object.source_gas_amount = source
            self.object.gas_type = batch.gas_type
            self.object.save()


class AutoTtnUpdateView(generic.UpdateView):
    model = AutoTtn
    form_class = AutoTtnForm
    template_name = 'filling_station/_equipment_form.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        self.update_ttn_values()
        return response

    def update_ttn_values(self):
        batch = self.object.batch
        if batch:
            settings = AutoGasBatchSettings.objects.first()

            if settings and settings.weight_source == 'f':
                self.object.total_gas_amount = batch.gas_amount
                self.object.source_gas_amount = 'Расходомер'
            else:
                self.object.total_gas_amount = batch.weight_gas_amount
                self.object.source_gas_amount = 'Весы'

            self.object.gas_type = batch.gas_type
            self.object.save()


class AutoTtnDeleteView(generic.DeleteView):
    model = AutoTtn
    success_url = reverse_lazy("filling_station:auto_ttn_list")
    template_name = 'filling_station/autottn_confirm_delete.html'


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

    # Получаем количество партий для каждой модели за период
    batches_data = {
        'balloons_loading_batches': BalloonsLoadingBatch.objects.filter(
            begin_date__range=[start_date, end_date]
        ).count(),
        'balloons_unloading_batches': BalloonsUnloadingBatch.objects.filter(
            begin_date__range=[start_date, end_date]
        ).count(),
        'auto_gas_loading_batches': AutoGasBatch.objects.filter(
            batch_type='l',
            begin_date__range=[start_date, end_date]
        ).count(),
        'auto_gas_unloading_batches': AutoGasBatch.objects.filter(
            batch_type='u',
            begin_date__range=[start_date, end_date]
        ).count(),
        'railway_batches': RailwayBatch.objects.filter(
            begin_date__range=[start_date, end_date]
        ).count(),
    }

    # Объединяем данные в контекст
    context = {
        **readers_data,
        **batches_data,
        'form': form,
        'start_date': start_date,
        'end_date': end_date,
    }

    return render(request, "statistic.html", context)
