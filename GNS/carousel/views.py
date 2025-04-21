from django.shortcuts import render
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.urls import reverse_lazy, reverse
from django.views import generic
from datetime import datetime
from .models import Carousel, CarouselSettings
from .admin import CarouselResources
from .forms import CarouselSettingsForm, GetCarouselBalloonsAmount


def carousel_info(request, carousel_number=1):
    current_date = datetime.now().date()

    if request.method == "POST":
        form = GetCarouselBalloonsAmount(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            size = form.cleaned_data['size']
        else:
            start_date = current_date
            end_date = current_date
            size = None

        action = request.POST.get('action')

        if action == 'export':
            queryset = Carousel.objects.filter(
                carousel_number=carousel_number,
                change_date__range=(start_date, end_date)
            )
            if size:
                queryset = queryset.filter(size=size)

            dataset = CarouselResources().export(queryset)
            response = HttpResponse(dataset.xlsx, content_type='xlsx')
            response[
                'Content-Disposition'] = f'attachment; filename="Carousel_{carousel_number}_{start_date}-{end_date}.xlsx"'
            return response

    else:
        form = GetCarouselBalloonsAmount()
        start_date = current_date
        end_date = current_date
        size = None

    carousel_list = Carousel.objects.all()

    if size:
        total_count = carousel_list.filter(
            carousel_number=carousel_number,
            change_date__range=(start_date, end_date),
            size=size
        ).count()
    else:
        total_count = carousel_list.filter(
            carousel_number=carousel_number,
            change_date__range=(start_date, end_date)
        ).count()

    paginator = Paginator(carousel_list, 10)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        "page_obj": page_obj,
        'form': form,
        'carousel_number': carousel_number,
        'start_date': start_date,
        'end_date': end_date,
        'selected_size': size,
        'total_count': total_count
    }
    return render(request, "carousel/carousel_list.html", context)


class CarouselSettingsDetailView(generic.DetailView):
    model = CarouselSettings
    template_name = 'carousel/carousel_settings_detail.html'
    context_object_name = 'carousel_settings'

    def get_object(self, queryset=None):
        return CarouselSettings.objects.first()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['posts'] = list(range(1, 21))
        return context


class CarouselSettingsUpdateView(generic.UpdateView):
    model = CarouselSettings
    form_class = CarouselSettingsForm
    template_name = 'carousel/_equipment_form.html'

    def get_object(self, queryset=None):
        return CarouselSettings.objects.first()

    def get_success_url(self):
        return reverse('carousel:carousel_settings_detail')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['posts'] = list(range(1, 21))
        return context
