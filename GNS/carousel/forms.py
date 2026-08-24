from django import forms
from django.utils import timezone
from .models import CarouselSettings
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML
from crispy_forms.bootstrap import FormActions
from crispy_forms.layout import Submit
from django.conf import settings


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

        post_fields = [f'post_{i}_correction' for i in range(1, 21)]
        layout_items = [
            'read_only',
            'use_weight_management',
            'use_common_correction',
            'weight_correction_value',
        ]
        for field_from, field_to, title in RANGE_FIELDS:
            layout_items.extend([
                HTML(f'<div class="mb-2 mt-3 fw-semibold">{title}</div>'),
                Row(
                    Column(field_from, css_class='col-md-6'),
                    Column(field_to, css_class='col-md-6'),
                ),
            ])
        layout_items.extend([
            HTML('<div class="mb-2 mt-3 fw-semibold">Корректоры постов</div>'),
            *post_fields,
            FormActions(
                Submit('save', 'Сохранить', css_class='btn btn-success'),
                Submit('cancel', 'Отмена', css_class='btn btn-secondary'),
            ),
        ])

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
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
        return cleaned_data

    class Meta:
        model = CarouselSettings
        exclude = ['user']
        widgets = {
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
