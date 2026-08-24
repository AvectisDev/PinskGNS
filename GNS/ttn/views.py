from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.http import HttpResponseRedirect
from core.mixins import ModalDeleteMixin, PreserveListQueryMixin
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import generic
from django.contrib import messages
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from .models import BalloonTtn, RailwayTtn, AutoTtn
from autogas.models import AutoGasBatchSettings
from .forms import BalloonTtnForm, AutoTtnForm, RailwayTtnForm
from .services import save_auto_ttn, save_balloon_ttn, save_railway_ttn, get_railway_ttn_gas_totals, get_railway_ttn_tank_rows


BALLOON_TTN_RELATED = (
    'shipper',
    'consignee',
    'carrier',
    'city',
    'loading_batch',
    'unloading_batch',
)
RAILWAY_TTN_RELATED = ('shipper', 'consignee', 'carrier')
AUTO_TTN_RELATED = (
    'shipper',
    'consignee',
    'carrier',
    'city',
    'batch__truck',
)


# ТТН для баллонов
class TTNView(generic.ListView):
    model = BalloonTtn
    paginate_by = 10
    queryset = BalloonTtn.objects.select_related(*BALLOON_TTN_RELATED)


class TTNDetailView(generic.DetailView):
    model = BalloonTtn
    queryset = BalloonTtn.objects.select_related(*BALLOON_TTN_RELATED)


class TTNCreateView(PreserveListQueryMixin, generic.CreateView):
    model = BalloonTtn
    form_class = BalloonTtnForm
    template_name = 'ttn/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        self.object = form.save(commit=False)
        save_balloon_ttn(self.object)
        messages.success(self.request, f'ТТН {self.object.number} успешно создана')
        return HttpResponseRedirect(self.get_success_url())


class TTNUpdateView(PreserveListQueryMixin, generic.UpdateView):
    model = BalloonTtn
    form_class = BalloonTtnForm
    template_name = 'ttn/_equipment_form.html'
    queryset = BalloonTtn.objects.select_related(*BALLOON_TTN_RELATED)

    def get_success_url(self):
        return self.object.get_absolute_url()

    def post(self, request, *args, **kwargs):
        if 'cancel' in request.POST:
            return self.redirect_preserve_query('ttn:ttn_detail', pk=self.get_object().pk)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        save_balloon_ttn(self.object)
        messages.success(self.request, f'ТТН {self.object.number} успешно обновлена')
        return HttpResponseRedirect(self.get_success_url())


class TTNDeleteView(ModalDeleteMixin, PreserveListQueryMixin, generic.DeleteView):
    model = BalloonTtn
    success_url = reverse_lazy("ttn:ttn_list")


# ТТН для жд цистерн
class RailwayTtnView(generic.ListView):
    model = RailwayTtn
    paginate_by = 10
    queryset = RailwayTtn.objects.select_related(*RAILWAY_TTN_RELATED)


class RailwayTtnDetailView(generic.DetailView):
    model = RailwayTtn
    queryset = (
        RailwayTtn.objects
        .select_related(*RAILWAY_TTN_RELATED)
        .prefetch_related('railway_tank_list__tank_history')
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['gas_totals'] = get_railway_ttn_gas_totals(self.object.railway_ttn)
        context['tank_rows'] = get_railway_ttn_tank_rows(self.object.railway_ttn)
        return context


class RailwayTtnCreateView(PreserveListQueryMixin, generic.CreateView):
    model = RailwayTtn
    form_class = RailwayTtnForm
    template_name = 'ttn/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        self.object = form.save(commit=False)
        save_railway_ttn(self.object, form.cleaned_data['railway_ttn'])
        messages.success(self.request, f'ТТН {self.object.number} успешно создана')
        return HttpResponseRedirect(self.get_success_url())


class RailwayTtnUpdateView(PreserveListQueryMixin, generic.UpdateView):
    model = RailwayTtn
    form_class = RailwayTtnForm
    template_name = 'ttn/_equipment_form.html'
    queryset = RailwayTtn.objects.select_related(*RAILWAY_TTN_RELATED)

    def get_success_url(self):
        return self.object.get_absolute_url()

    def post(self, request, *args, **kwargs):
        if 'cancel' in request.POST:
            return self.redirect_preserve_query('ttn:railway_ttn_detail', pk=self.get_object().pk)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        save_railway_ttn(self.object, form.cleaned_data['railway_ttn'])
        return HttpResponseRedirect(self.get_success_url())


class RailwayTtnDeleteView(ModalDeleteMixin, PreserveListQueryMixin, generic.DeleteView):
    model = RailwayTtn
    success_url = reverse_lazy("ttn:railway_ttn_list")


# ТТН для автоцистерн
@login_required
@require_POST
def update_weight_source(request):
    weight_source = request.POST.get('weight_source')
    if weight_source not in ('f', 's'):
        weight_source = 's'
    settings, _ = AutoGasBatchSettings.objects.get_or_create()
    settings.weight_source = weight_source
    settings.save()
    return redirect('ttn:auto_ttn_list')


@method_decorator(ensure_csrf_cookie, name='dispatch')
class AutoTtnView(generic.ListView):
    model = AutoTtn
    paginate_by = 10
    queryset = AutoTtn.objects.select_related(*AUTO_TTN_RELATED)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        settings = AutoGasBatchSettings.objects.first()
        context['weight_source'] = settings.weight_source if settings else 'f'
        return context


class AutoTtnDetailView(generic.DetailView):
    model = AutoTtn
    queryset = AutoTtn.objects.select_related(*AUTO_TTN_RELATED)


class AutoTtnCreateView(PreserveListQueryMixin, generic.CreateView):
    model = AutoTtn
    form_class = AutoTtnForm
    template_name = 'ttn/_equipment_form.html'

    def form_valid(self, form):
        self.object = form.save(commit=False)
        save_auto_ttn(self.object)
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return self.object.get_absolute_url()


class AutoTtnUpdateView(PreserveListQueryMixin, generic.UpdateView):
    model = AutoTtn
    form_class = AutoTtnForm
    template_name = 'ttn/_equipment_form.html'
    queryset = AutoTtn.objects.select_related(*AUTO_TTN_RELATED)

    def get_success_url(self):
        return self.object.get_absolute_url()

    def post(self, request, *args, **kwargs):
        if 'cancel' in request.POST:
            return self.redirect_preserve_query('ttn:auto_ttn_detail', pk=self.get_object().pk)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        save_auto_ttn(self.object)
        return HttpResponseRedirect(self.get_success_url())


class AutoTtnDeleteView(ModalDeleteMixin, PreserveListQueryMixin, generic.DeleteView):
    model = AutoTtn
    success_url = reverse_lazy("ttn:auto_ttn_list")
