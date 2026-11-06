from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.urls import reverse
from django.views import generic
from datetime import datetime, time
from .models import Carousel, CarouselSettings
from .admin import CarouselResources
from .forms import CarouselSettingsForm, GetCarouselBalloonsAmount


def _date_range_bounds(start_date, end_date):
    date_start = datetime.combine(start_date, time.min)
    date_end = datetime.combine(
        start_date if start_date == end_date else end_date,
        time.max,
    )
    return date_start, date_end


def carousel_info(request, carousel_number=1):
    current_date = datetime.now().date()
    size = None

    if request.method == "POST":
        form = GetCarouselBalloonsAmount(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            size = form.cleaned_data['size'] or None
        else:
            start_date = current_date
            end_date = current_date
    else:
        form = GetCarouselBalloonsAmount()
        start_date = current_date
        end_date = current_date

    date_start, date_end = _date_range_bounds(start_date, end_date)
    queryset = Carousel.objects.filter(
        carousel_number=carousel_number,
        change_at__range=(date_start, date_end),
    )
    if size:
        queryset = queryset.filter(size=size)

    if request.method == "POST" and request.POST.get('action') == 'export':
        dataset = CarouselResources().export(queryset)
        response = HttpResponse(dataset.xlsx, content_type='xlsx')
        response['Content-Disposition'] = (
            f'attachment; filename="Carousel_{carousel_number}_{start_date}-{end_date}.xlsx"'
        )
        return response

    total_count = queryset.count()
    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page', 1))

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


class CarouselSettingsListView(generic.ListView):
    model = CarouselSettings
    template_name = 'carousel/carousel_settings_list.html'
    context_object_name = 'carousel_settings_list'


class CarouselSettingsDetailView(generic.DetailView):
    model = CarouselSettings
    template_name = 'carousel/carousel_settings_detail.html'
    context_object_name = 'carousel_settings'
    slug_field = 'number'
    slug_url_kwarg = 'number'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['posts'] = list(range(1, 21))
        return context


class CarouselSettingsUpdateView(generic.UpdateView):
    model = CarouselSettings
    form_class = CarouselSettingsForm
    template_name = 'carousel/_equipment_form.html'
    slug_field = 'number'
    slug_url_kwarg = 'number'

    def get_success_url(self):
        return reverse(
            'carousel:carousel_settings_detail',
            kwargs={'number': self.object.number},
        )

    def post(self, request, *args, **kwargs):
        if 'cancel' in request.POST:
            return redirect(
                'carousel:carousel_settings_detail',
                number=self.get_object().number,
            )
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['posts'] = list(range(1, 21))
        return context
