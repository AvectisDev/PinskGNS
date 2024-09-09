from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.core.paginator import Paginator
from .models import (Balloon, Truck, Trailer, RailwayTanks, TTN, BalloonsLoadingBatch, BalloonsUnloadingBatch,
                     RailwayLoadingBatch, BalloonAmount, GasLoadingBatch, GasUnloadingBatch)
from .admin import BalloonResources
from .forms import (GetBalloonsAmount, BalloonPassportForm, TruckForm, TrailerForm, RailwayTanksForm, TTNForm,
                    BalloonsLoadingBatchForm, BalloonsUnloadingBatchForm, RailwayLoadingBatchForm, GasLoadingBatchForm,
                    GasUnloadingBatchForm)
from datetime import datetime, timedelta
from django.http import Http404

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

def balloons(request):
    nfc_tag_filter = request.GET.get('nfc_tag', '')
    if nfc_tag_filter:
        balloons_list = Balloon.objects.filter(nfc_tag=nfc_tag_filter)
    else:
        balloons_list = Balloon.objects.all()
    #
    paginator = Paginator(balloons_list, 15)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        "page_obj": page_obj,
        "nfc_tag_filter": nfc_tag_filter
    }
    return render(request, "balloons_table.html", context)


def balloon_passport(request, nfc_tag):
    try:
        balloon = Balloon.objects.filter(nfc_tag=nfc_tag).first()

        if request.method == 'POST':
            form = BalloonPassportForm(request.POST, instance=balloon)
            if form.is_valid():
                balloon = form.save()
                return redirect('filling_station:balloons_list')
        else:
            form = BalloonPassportForm(instance=balloon)

            context = {
                "balloon": balloon,
                'form': form
            }
            return render(request, "balloon_passport.html", context)
    except:
        raise Http404("No Balloon found")


def reader_info(request, reader='1'):
    current_date = datetime.now().date()
    previous_date = current_date - timedelta(days=1)

    if request.method == "POST":
        required_date = request.POST.get("date")
        format_required_date = datetime.strptime(required_date, '%d.%m.%Y')
        dataset = BalloonResources().export(Balloon.objects.order_by('-id').filter(status=STATUS_LIST[reader],
                                                                                   change_date=format_required_date))
        response = HttpResponse(dataset.xls, content_type='xls')
        response['Content-Disposition'] = f'attachment; filename="RFID_1_{datetime.strftime(format_required_date, '%Y.%m.%d')}.xls"'
        return response
    else:
        date_process = GetBalloonsAmount()

    balloons_list = Balloon.objects.order_by('-id').filter(status=STATUS_LIST[reader])
    current_quantity_by_sensor = BalloonAmount.objects.filter(reader_id=reader, change_date=current_date)
    previous_quantity_by_sensor = BalloonAmount.objects.filter(reader_id=reader, change_date=previous_date)
    current_quantity_by_reader = len(balloons_list.filter(change_date=current_date))
    previous_quantity_by_reader = len(balloons_list.filter(change_date=previous_date))

    paginator = Paginator(balloons_list, 15)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    current_quantity_by_sensor_item = previous_quantity_by_sensor_item = 0
    for amount in current_quantity_by_sensor:
        current_quantity_by_sensor_item = amount.amount_of_balloons
    for amount in previous_quantity_by_sensor:
        previous_quantity_by_sensor_item = amount.amount_of_balloons

    context = {
        "page_obj": page_obj,
        'current_quantity_by_reader': current_quantity_by_reader,
        'previous_quantity_by_reader': previous_quantity_by_reader,
        'current_quantity_by_sensor': current_quantity_by_sensor_item,
        'previous_quantity_by_sensor': previous_quantity_by_sensor_item,
        'form': date_process,
        'reader': reader
    }
    return render(request, "rfid_tables.html", context)


def balloons_loading_batch(request):
    batch_list = BalloonsLoadingBatch.objects.all()

    paginator = Paginator(batch_list, 15)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        "page_obj": page_obj,
    }
    return render(request, "balloons_loading_batch.html", context)


def balloons_loading_batch_details(request, number: int):
    try:

        batch = get_object_or_404(BalloonsLoadingBatch, id=number)

        if request.method == 'POST':
            form = BalloonsLoadingBatchForm(request.POST, instance=batch)
            if form.is_valid():
                form.save()
                return redirect('filling_station:balloons_loading_batch')
        else:
            form = BalloonsLoadingBatchForm(instance=batch)

        context = {
            'batch': batch,
            'form': form
        }
        return render(request, "balloons_batch_details.html", context)

    except BalloonsLoadingBatch.DoesNotExist:
        raise Http404("Партия не найдена")


def balloons_unloading_batch(request):
    batch_list = BalloonsUnloadingBatch.objects.all()

    paginator = Paginator(batch_list, 15)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        'page_obj': page_obj,
    }
    return render(request, "balloons_unloading_batch.html", context)


def balloons_unloading_batch_details(request, number: int):
    try:

        batch = get_object_or_404(BalloonsUnloadingBatch, id=number)

        if request.method == 'POST':
            form = BalloonsUnloadingBatchForm(request.POST, instance=batch)
            if form.is_valid():
                form.save()
                return redirect('filling_station:balloons_unloading_batch')
        else:
            form = BalloonsUnloadingBatchForm(instance=batch)

        context = {
            'batch': batch,
            'form': form
        }
        return render(request, "balloons_batch_details.html", context)

    except BalloonsUnloadingBatch.DoesNotExist:
        raise Http404("Партия не найдена")


def gas_loading_batch(request):
    batch_list = GasLoadingBatch.objects.all()

    paginator = Paginator(batch_list, 15)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        "page_obj": page_obj,
    }
    return render(request, "auto_gas_loading_batch.html", context)


def gas_loading_batch_details(request, number: int):
    try:

        batch = get_object_or_404(GasLoadingBatch, id=number)

        if request.method == 'POST':
            form = GasLoadingBatchForm(request.POST, instance=batch)
            if form.is_valid():
                form.save()
                return redirect('filling_station:auto_gas_loading_batch')
        else:
            form = GasLoadingBatchForm(instance=batch)

        context = {
            'batch': batch,
            'form': form
        }
        return render(request, "auto_gas_batch_details.html", context)

    except GasLoadingBatch.DoesNotExist:
        raise Http404("Партия не найдена")


def gas_unloading_batch(request):
    batch_list = GasUnloadingBatch.objects.all()

    paginator = Paginator(batch_list, 15)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        "page_obj": page_obj,
    }
    return render(request, "auto_gas_unloading_batch.html", context)


def gas_unloading_batch_details(request, number: int):
    try:

        batch = get_object_or_404(GasUnloadingBatch, id=number)

        if request.method == 'POST':
            form = GasUnloadingBatchForm(request.POST, instance=batch)
            if form.is_valid():
                form.save()
                return redirect('filling_station:auto_gas_unloading_batch')
        else:
            form = GasUnloadingBatchForm(instance=batch)

        context = {
            'batch': batch,
            'form': form
        }
        return render(request, "auto_gas_batch_details.html", context)

    except GasUnloadingBatch.DoesNotExist:
        raise Http404("Партия не найдена")


def railway_loading_batch(request):
    batch_list = RailwayLoadingBatch.objects.all()

    paginator = Paginator(batch_list, 15)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        "page_obj": page_obj,
    }
    return render(request, "railway_loading_batch.html", context)


def railway_loading_batch_details(request, number: int):
    try:

        batch = get_object_or_404(RailwayLoadingBatch, id=number)

        if request.method == 'POST':
            form = RailwayLoadingBatchForm(request.POST, instance=batch)
            if form.is_valid():
                form.save()
                return redirect('filling_station:railway_loading_batch')
        else:
            form = RailwayLoadingBatchForm(instance=batch)

        context = {
            'batch': batch,
            'form': form
        }
        return render(request, "railway_loading_batch_details.html", context)

    except RailwayLoadingBatch.DoesNotExist:
        raise Http404("Партия не найдена")


def get_trucks(request):
    truck_list = Truck.objects.all()

    paginator = Paginator(truck_list, 15)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        'page_obj': page_obj,
    }
    return render(request, "trucks_table.html", context)


def get_trucks_details(request, number: str):
    try:

        truck = get_object_or_404(Truck, registration_number=number)

        if request.method == 'POST':
            form = TruckForm(request.POST, instance=truck)
            if form.is_valid():
                form.save()
                return redirect('filling_station:trucks')
        else:
            form = TruckForm(instance=truck)

        context = {
            'truck': truck,
            'form': form
        }
        return render(request, "transport_details.html", context)

    except Truck.DoesNotExist:
        raise Http404("Грузовик не найден")


def get_trailers(request):
    trailers_list = Trailer.objects.all()

    paginator = Paginator(trailers_list, 15)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        'page_obj': page_obj,
    }
    return render(request, "trailers_table.html", context)


def get_trailers_details(request, number: str):
    try:

        trailer = get_object_or_404(Trailer, registration_number=number)

        if request.method == 'POST':
            form = TrailerForm(request.POST, instance=trailer)
            if form.is_valid():
                form.save()
                return redirect('filling_station:trailers')
        else:
            form = TrailerForm(instance=trailer)

        context = {
            'trailer': trailer,
            'form': form
        }
        return render(request, "transport_details.html", context)

    except Trailer.DoesNotExist:
        raise Http404("Прицеп не найден")


def get_railway_tanks(request):
    railway_tanks_list = RailwayTanks.objects.all()

    paginator = Paginator(railway_tanks_list, 15)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        'page_obj': page_obj,
    }
    return render(request, "railway_tanks_table.html", context)


def get_railway_tanks_details(request, number: int):
    try:

        railway_tank = get_object_or_404(RailwayTanks, id=number)

        if request.method == 'POST':
            form = RailwayTanksForm(request.POST, instance=railway_tank)
            if form.is_valid():
                form.save()
                return redirect('filling_station:railway_tanks')
        else:
            form = RailwayTanksForm(instance=railway_tank)

        context = {
            'railway_tank': railway_tank,
            'form': form
        }
        return render(request, "transport_details.html", context)

    except RailwayTanks.DoesNotExist:
        raise Http404("Цистерна не найдена")


def get_ttn(request):
    ttn_list = TTN.objects.all()

    paginator = Paginator(ttn_list, 15)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        'page_obj': page_obj,
    }
    return render(request, "ttn_table.html", context)


def get_ttn_details(request, number: int):
    try:

        ttn = get_object_or_404(TTN, id=number)

        if request.method == 'POST':
            form = TTNForm(request.POST, instance=ttn)
            if form.is_valid():
                form.save()
                return redirect('filling_station:get_ttn')
        else:
            form = TTNForm(instance=ttn)

        context = {
            'ttn': ttn,
            'form': form
        }
        return render(request, "ttn_details.html", context)

    except TTN.DoesNotExist:
        raise Http404("ТТН не найдена")
