"""Веб-представления грузовиков и прицепов."""

from django.db.models import Q
from django.urls import reverse_lazy
from django.views import generic

from core.mixins import CancelFormMixin, ModalDeleteMixin, PreserveListQueryMixin
from transport.forms import TrailerForm, TruckForm
from transport.models import Trailer, Truck


class TruckView(generic.ListView):
    """Список тягачей с поиском по госномеру или марке."""

    model = Truck
    paginate_by = 10
    template_name = 'transport/truck_list.html'

    def get_queryset(self):
        queryset = (
            super().get_queryset()
            .select_related('type', 'driver')
            .exclude(car_brand__iexact='Самовывоз')
        )
        query = self.request.GET.get('query', '').strip()
        if query:
            queryset = queryset.filter(
                Q(registration_number__icontains=query) | Q(car_brand__icontains=query)
            )
        return queryset


class TruckDetailView(generic.DetailView):
    """Карточка тягача."""

    model = Truck
    template_name = 'transport/truck_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related('type', 'driver')


class TruckCreateView(CancelFormMixin, PreserveListQueryMixin, generic.CreateView):
    """Создание записи тягача."""

    model = Truck
    form_class = TruckForm
    template_name = 'transport/_equipment_form.html'
    cancel_url = reverse_lazy('transport:truck_list')

    def get_success_url(self):
        return self.object.get_absolute_url()


class TruckUpdateView(PreserveListQueryMixin, generic.UpdateView):
    """Редактирование тягача."""

    model = Truck
    form_class = TruckForm
    template_name = 'transport/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def post(self, request, *args, **kwargs):
        if 'cancel' in request.POST:
            return self.redirect_preserve_query('transport:truck_detail', pk=self.get_object().pk)
        return super().post(request, *args, **kwargs)


class TruckDeleteView(ModalDeleteMixin, PreserveListQueryMixin, generic.DeleteView):
    """Удаление тягача через модальное окно."""

    model = Truck
    success_url = reverse_lazy('transport:truck_list')


class TrailerView(generic.ListView):
    """Список прицепов с поиском по госномеру или марке."""

    model = Trailer
    paginate_by = 10
    template_name = 'transport/trailer_list.html'

    def get_queryset(self):
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
    template_name = 'transport/trailer_detail.html'


class TrailerCreateView(CancelFormMixin, PreserveListQueryMixin, generic.CreateView):
    """Создание записи прицепа."""

    model = Trailer
    form_class = TrailerForm
    template_name = 'transport/_equipment_form.html'
    cancel_url = reverse_lazy('transport:trailer_list')

    def get_success_url(self):
        return self.object.get_absolute_url()


class TrailerUpdateView(PreserveListQueryMixin, generic.UpdateView):
    """Редактирование прицепа."""

    model = Trailer
    form_class = TrailerForm
    template_name = 'transport/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def post(self, request, *args, **kwargs):
        if 'cancel' in request.POST:
            return self.redirect_preserve_query('transport:trailer_detail', pk=self.get_object().pk)
        return super().post(request, *args, **kwargs)


class TrailerDeleteView(ModalDeleteMixin, PreserveListQueryMixin, generic.DeleteView):
    """Удаление прицепа через модальное окно."""

    model = Trailer
    success_url = reverse_lazy('transport:trailer_list')
