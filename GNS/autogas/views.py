from django.urls import reverse_lazy, reverse
from django.views import generic
from .models import AutoGasBatch
from .forms import AutoGasBatchForm
from django.shortcuts import redirect


# Партии автоцистерн
class AutoGasBatchListView(generic.ListView):
    model = AutoGasBatch
    paginate_by = 10
    template_name = 'autogas/auto_batch_list.html'


class AutoGasBatchDetailView(generic.DetailView):
    model = AutoGasBatch
    context_object_name = 'batch'
    template_name = 'autogas/auto_batch_detail.html'


class AutoGasBatchUpdateView(generic.UpdateView):
    model = AutoGasBatch
    form_class = AutoGasBatchForm
    template_name = 'autogas/_equipment_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def post(self, request, *args, **kwargs):
        if 'cancel' in request.POST:
            return redirect('autogas:auto_gas_batch_detail', pk=self.get_object().pk)
        return super().post(request, *args, **kwargs)


class AutoGasBatchDeleteView(generic.DeleteView):
    model = AutoGasBatch
    success_url = reverse_lazy("autogas:auto_gas_batch_list")
    template_name = 'autogas/auto_batch_confirm_delete.html'
