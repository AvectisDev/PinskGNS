from django.urls import reverse_lazy, reverse
from django.views import generic
from .models import RailwayTank, RailwayBatch
from .forms import RailwayTankForm, RailwayBatchForm


# ж/д цистерны
class RailwayTankView(generic.ListView):
    model = RailwayTank
    paginate_by = 10


class RailwayTankDetailView(generic.DetailView):
    model = RailwayTank


class RailwayTankCreateView(generic.CreateView):
    model = RailwayTank
    form_class = RailwayTankForm
    template_name = 'railway_service/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()


class RailwayTankUpdateView(generic.UpdateView):
    model = RailwayTank
    form_class = RailwayTankForm
    template_name = 'railway_service/_equipment_form.html'


class RailwayTankDeleteView(generic.DeleteView):
    model = RailwayTank
    success_url = reverse_lazy("railway_service:railway_tank_list")
    template_name = 'railway_service/railway_tank_confirm_delete.html'


# Партии приёмки газа в ж/д цистернах
class RailwayBatchListView(generic.ListView):
    model = RailwayBatch
    paginate_by = 10
    template_name = 'railway_service/railway_batch_list.html'


class RailwayBatchDetailView(generic.DetailView):
    model = RailwayBatch
    queryset = RailwayBatch.objects.prefetch_related('railway_tank_list')
    context_object_name = 'batch'
    template_name = 'railway_service/railway_batch_detail.html'


class RailwayBatchUpdateView(generic.UpdateView):
    model = RailwayBatch
    form_class = RailwayBatchForm
    template_name = 'railway_service/_equipment_form.html'


class RailwayBatchDeleteView(generic.DeleteView):
    model = RailwayBatch
    success_url = reverse_lazy("railway_service:railway_batch_list")
    template_name = 'railway_service/railway_batch_confirm_delete.html'
