from django import forms
from django.utils import timezone
from .models import CarouselSettings
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, HTML, Div, Submit, Field
from crispy_forms.bootstrap import InlineField
from django.conf import settings


CHECKBOX_TEMPLATE = 'carousel/crispy/horizontal_checkbox.html'


class GetCarouselBalloonsAmount(forms.Form):
    start_date = forms.DateField(
        label="Начальная дата",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=timezone.now().date()
    )
    end_date = forms.DateField(
        label="Конечная дата",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=timezone.now().date()
    )
    size = forms.ChoiceField(
        label="Объем баллона",
        choices=[('', 'Все объемы')] + list(settings.BALLOON_SIZE_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.form_method = 'POST'


RANGE_FIELDS = (
    ('min_balloon_weight_from', 'min_balloon_weight_to', 'Минимальный вес баллона, кг'),
    ('max_balloon_weight_from', 'max_balloon_weight_to', 'Максимальный вес баллона, кг'),
    ('passport_weight_diff_from', 'passport_weight_diff_to', 'Разница паспортных весов, кг'),
)


class CarouselSettingsForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_from, field_to, _ in RANGE_FIELDS:
            self.fields[field_from].label = 'от'
            self.fields[field_to].label = 'до'

        layout_items = [
            HTML('<div class="mb-2 mt-3 fw-semibold">Оборудование</div>'),
            'number',
            'name',
            'tcp_host',
            'tcp_port',
            'rfid_reader',
            Field('is_active', template=CHECKBOX_TEMPLATE),
            HTML('<div class="mb-2 mt-3 fw-semibold">Весовая политика</div>'),
            Field('read_only', template=CHECKBOX_TEMPLATE),
            Field('use_weight_management', template=CHECKBOX_TEMPLATE),
            Field('use_common_correction', template=CHECKBOX_TEMPLATE),
            'weight_correction_value',
        ]
        for field_from, field_to, title in RANGE_FIELDS:
            layout_items.append(
                Div(
                    HTML(
                        f'<label class="col-lg-5 col-form-label text-lg-end">{title} от</label>'
                    ),
                    Div(
                        InlineField(field_from, wrapper_class='flex-fill'),
                        HTML('<span class="col-form-label text-nowrap px-1">до</span>'),
                        InlineField(field_to, wrapper_class='flex-fill'),
                        css_class='col-lg-3 d-flex align-items-center gap-1',
                    ),
                    css_class='mb-3 row align-items-center',
                )
            )
        layout_items.extend([
            HTML('<div class="mb-2 mt-3 fw-semibold">Корректоры постов</div>'),
            *[f'post_{i}_correction' for i in range(1, 21)],
            Div(
                HTML('<div class="col-lg-5"></div>'),
                Div(
                    Submit('save', 'Сохранить', css_class='btn btn-success'),
                    Submit('cancel', 'Отмена', css_class='btn btn-secondary', formnovalidate='formnovalidate'),
                    css_class='col-lg-auto d-flex gap-2',
                ),
                css_class='mb-3 row',
            ),
        ])

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-5 text-lg-end'
        self.helper.field_class = 'col-lg-3'
        self.helper.form_method = 'POST'
        self.helper.layout = Layout(*layout_items)

    def clean(self):
        cleaned_data = super().clean()
        for field_from, field_to, title in RANGE_FIELDS:
            value_from = cleaned_data.get(field_from)
            value_to = cleaned_data.get(field_to)
            if value_from is not None and value_to is not None and value_from > value_to:
                raise forms.ValidationError(
                    f'{title}: значение «от» не может быть больше значения «до».'
                )

        is_active = cleaned_data.get('is_active')
        tcp_host = (cleaned_data.get('tcp_host') or '').strip()
        rfid_reader = cleaned_data.get('rfid_reader')
        if is_active:
            if not tcp_host:
                self.add_error(
                    'tcp_host',
                    'Для активной карусели необходимо указать IP NPort.',
                )
            if rfid_reader is None:
                self.add_error(
                    'rfid_reader',
                    'Для активной карусели необходимо указать RFID-считыватель.',
                )
        return cleaned_data

    class Meta:
        model = CarouselSettings
        exclude = ['user', 'classify_size_by_weight', 'size_27_empty_weight_max_g']
        widgets = {
            'number': forms.NumberInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'tcp_host': forms.TextInput(attrs={'class': 'form-control'}),
            'tcp_port': forms.NumberInput(attrs={'class': 'form-control'}),
            'rfid_reader': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'read_only': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'use_weight_management': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'weight_correction_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'use_common_correction': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'min_balloon_weight_from': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'min_balloon_weight_to': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'max_balloon_weight_from': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'max_balloon_weight_to': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'passport_weight_diff_from': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'passport_weight_diff_to': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_1_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_2_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_3_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_4_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_5_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_6_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_7_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_8_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_9_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_10_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_11_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_12_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_13_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_14_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_15_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_16_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_17_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_18_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_19_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_20_correction': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
