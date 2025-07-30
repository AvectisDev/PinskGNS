from django.shortcuts import render, redirect
from django.urls import reverse_lazy, reverse
from django.views import generic
from django.db.models import Q, Sum
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import RailwayTank, BalloonTtn, RailwayTtn, AutoTtn
from autogas.models import AutoGasBatchSettings
from .forms import BalloonTtnForm, AutoTtnForm, RailwayTtnForm


# ТТН для баллонов
class TTNView(generic.ListView):
    model = BalloonTtn
    paginate_by = 10


class TTNDetailView(generic.DetailView):
    model = BalloonTtn


class TTNCreateView(generic.CreateView):
    model = BalloonTtn
    form_class = BalloonTtnForm
    template_name = 'ttn/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'ТТН {self.object.number} успешно создана')
        return response


class TTNUpdateView(generic.UpdateView):
    model = BalloonTtn
    form_class = BalloonTtnForm
    template_name = 'ttn/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'ТТН {self.object.number} успешно обновлена')
        return response


class TTNDeleteView(generic.DeleteView):
    model = BalloonTtn
    success_url = reverse_lazy("ttn:ttn_list")
    template_name = 'ttn/balloonttn_confirm_delete.html'


# ТТН для жд цистерн
class RailwayTtnView(generic.ListView):
    model = RailwayTtn
    paginate_by = 10


class RailwayTtnDetailView(generic.DetailView):
    model = RailwayTtn


class RailwayTtnCreateView(generic.CreateView):
    model = RailwayTtn
    form_class = RailwayTtnForm
    template_name = 'ttn/_equipment_form.html'

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
    template_name = 'ttn/_equipment_form.html'

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
    success_url = reverse_lazy("ttn:railway_ttn_list")
    template_name = 'ttn/railwayttn_confirm_delete.html'


# ТТН для автоцистерн
@require_POST
# @login_required
def update_weight_source(request):
    weight_source = request.POST.get('weight_source', 's')  # 'f' если чекбокс отмечен, иначе 's'
    settings, _ = AutoGasBatchSettings.objects.get_or_create()
    settings.weight_source = weight_source
    settings.save()
    return redirect('ttn:auto_ttn_list')


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
    template_name = 'ttn/_equipment_form.html'

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
    template_name = 'ttn/_equipment_form.html'

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
    success_url = reverse_lazy("ttn:auto_ttn_list")
    template_name = 'ttn/autottn_confirm_delete.html'
