from django.urls import reverse_lazy
from django.views import generic
from .models import AutoGasBatch
from .forms import AutoGasBatchForm
from core.mixins import ModalDeleteMixin, PreserveListQueryMixin


# Партии автоцистерн
class AutoGasBatchListView(generic.ListView):
    model = AutoGasBatch
    paginate_by = 10
    template_name = 'autogas/auto_batch_list.html'

    def get_queryset(self):
        return super().get_queryset().select_related('truck', 'trailer')


class AutoGasBatchDetailView(generic.DetailView):
    model = AutoGasBatch
    context_object_name = 'batch'
    template_name = 'autogas/auto_batch_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related('truck', 'trailer')


class AutoGasBatchUpdateView(PreserveListQueryMixin, generic.UpdateView):
    model = AutoGasBatch
    form_class = AutoGasBatchForm
    template_name = 'autogas/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def post(self, request, *args, **kwargs):
        if 'cancel' in request.POST:
            return self.redirect_preserve_query('autogas:auto_gas_batch_detail', pk=self.get_object().pk)
        return super().post(request, *args, **kwargs)


class AutoGasBatchDeleteView(ModalDeleteMixin, PreserveListQueryMixin, generic.DeleteView):
    model = AutoGasBatch
    success_url = reverse_lazy("autogas:auto_gas_batch_list")
