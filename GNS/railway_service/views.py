from django.urls import reverse_lazy
from django.views import generic
from django.shortcuts import redirect
from core.mixins import DateRangeListFilterMixin, ModalDeleteMixin, PreserveListQueryMixin
from .models import RailwayTank, RailwayBatch, RailwayTankHistory
from .forms import RailwayTankForm, RailwayBatchForm, RailwayTankHistoryForm
from django.db import transaction
from django.db.models import Prefetch, Max, Q


# ж/д цистерны
class RailwayTankView(generic.ListView):
    model = RailwayTank
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related(
            Prefetch(
                'tank_history',
                queryset=RailwayTankHistory.objects.order_by('-arrival_at')
            )
        ).annotate(
            latest_arrival=Max('tank_history__arrival_at')
        ).order_by('-is_on_station', 'latest_arrival')
        query = self.request.GET.get('query', '').strip()
        if query:
            queryset = queryset.filter(registration_number__icontains=query)
        return queryset


class RailwayTankDetailView(generic.DetailView):
    model = RailwayTank

    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            Prefetch(
                'tank_history',
                queryset=RailwayTankHistory.objects.order_by('-arrival_at')
            )
        )


class RailwayTankCreateView(PreserveListQueryMixin, generic.CreateView):
    model = RailwayTank
    form_class = RailwayTankForm
    template_name = 'railway_service/railway_tank_combined_edit.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get(self, request, *args, **kwargs):
        self.object = None
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if 'cancel' in request.POST:
            return self.redirect_preserve_query('railway_service:railway_tank_list')
        self.object = None
        tank_form = RailwayTankForm(request.POST, request.FILES, show_actions=False)
        history_form = RailwayTankHistoryForm(request.POST)
        # Проверка на дубликат номера
        reg_num = request.POST.get('registration_number')
        
        if tank_form.is_valid() and history_form.is_valid():
            with transaction.atomic():
                self.object = tank_form.save()
                history_instance = history_form.save(commit=False)
                history_instance.tank = self.object
                history_instance.save()
            return redirect(self.get_success_url())
        context = self.get_context_data(form=tank_form, history_form=history_form)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = kwargs.get('form') or RailwayTankForm(show_actions=False)
        context['history_form'] = kwargs.get('history_form') or RailwayTankHistoryForm()
        return context


class RailwayTankUpdateView(PreserveListQueryMixin, generic.UpdateView):
    model = RailwayTank
    form_class = RailwayTankForm
    template_name = 'railway_service/railway_tank_combined_edit.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def post(self, request, *args, **kwargs):
        if 'cancel' in request.POST:
            return self.redirect_preserve_query('railway_service:railway_tank_detail', pk=self.get_object().pk)
        self.object = self.get_object()
        tank_form = RailwayTankForm(request.POST, request.FILES, instance=self.object, show_actions=False)
        last_history = self.object.tank_history.all().first()
        if last_history is None:
            last_history = RailwayTankHistory(tank=self.object)
        history_form = RailwayTankHistoryForm(request.POST, instance=last_history)
        if tank_form.is_valid() and history_form.is_valid():
            with transaction.atomic():
                tank_form.save()
                history_form.save()
            return redirect(self.get_success_url())
        context = self.get_context_data(form=tank_form, history_form=history_form)
        return self.render_to_response(context)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Прячем внутренние кнопки в основной форме, т.к. используем общие кнопки в шаблоне
        kwargs['show_actions'] = False
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tank: RailwayTank = self.object
        # Всегда подменяем форму на вариант без внутренних кнопок
        context['form'] = kwargs.get('form') or RailwayTankForm(instance=tank, show_actions=False)
        last_history = tank.tank_history.all().first()
        if last_history is None:
            last_history = RailwayTankHistory(tank=tank)
        context['history_form'] = kwargs.get('history_form') or RailwayTankHistoryForm(instance=last_history)
        return context


class RailwayTankDeleteView(ModalDeleteMixin, PreserveListQueryMixin, generic.DeleteView):
    model = RailwayTank
    success_url = reverse_lazy("railway_service:railway_tank_list")


# Партии приёмки газа в ж/д цистернах
def _railway_batch_queryset():
    tank_history = Prefetch(
        'tank_history',
        queryset=RailwayTankHistory.objects.order_by('-arrival_at'),
    )
    return RailwayBatch.objects.prefetch_related(
        Prefetch(
            'railway_tank_list',
            queryset=RailwayTank.objects.prefetch_related(tank_history),
        )
    )


class RailwayBatchListView(DateRangeListFilterMixin, generic.ListView):
    model = RailwayBatch
    paginate_by = 10
    template_name = 'railway_service/railway_batch_list.html'

    def get_queryset(self):
        queryset = _railway_batch_queryset()
        return self.apply_date_range_filter(queryset, field_name='begin_date')


class RailwayBatchDetailView(generic.DetailView):
    model = RailwayBatch
    queryset = _railway_batch_queryset()
    context_object_name = 'batch'
    template_name = 'railway_service/railway_batch_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['gas_totals'] = self.object.get_gas_totals()
        return context


class RailwayBatchUpdateView(PreserveListQueryMixin, generic.UpdateView):
    model = RailwayBatch
    form_class = RailwayBatchForm
    template_name = 'railway_service/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def post(self, request, *args, **kwargs):
        if 'cancel' in request.POST:
            return self.redirect_preserve_query('railway_service:railway_batch_detail', pk=self.get_object().pk)
        return super().post(request, *args, **kwargs)


class RailwayBatchDeleteView(ModalDeleteMixin, PreserveListQueryMixin, generic.DeleteView):
    model = RailwayBatch
    success_url = reverse_lazy("railway_service:railway_batch_list")
