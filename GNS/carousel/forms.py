from crispy_forms.bootstrap import StrictButton
from django import forms
from django.utils import timezone
from .models import CarouselSettings
from .models import BALLOON_SIZE_CHOICES
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit


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
        choices=[('', 'Все объемы')] + list(BALLOON_SIZE_CHOICES),
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


class CarouselSettingsForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.add_input(Submit('Сохранить', 'Сохранить', css_class='btn btn-success'))
        self.helper.form_method = 'POST'

    class Meta:
        model = CarouselSettings
        fields = '__all__'
        widgets = {
            'read_only': forms.CheckboxInput(attrs={'class': 'form-control'}),
            'use_weight_management': forms.CheckboxInput(attrs={'class': 'form-control'}),
            'weight_correction_value': forms.NumberInput(attrs={'class': 'form-control'}),
            'use_common_correction': forms.CheckboxInput(attrs={'class': 'form-control'}),
            'post_1_correction': forms.NumberInput(attrs={'class': 'form-control'}),
            'post_2_correction': forms.NumberInput(attrs={'class': 'form-control'}),
            'post_3_correction': forms.NumberInput(attrs={'class': 'form-control'}),
            'post_4_correction': forms.NumberInput(attrs={'class': 'form-control'}),
            'post_5_correction': forms.NumberInput(attrs={'class': 'form-control'}),
            'post_6_correction': forms.NumberInput(attrs={'class': 'form-control'}),
            'post_7_correction': forms.NumberInput(attrs={'class': 'form-control'}),
            'post_8_correction': forms.NumberInput(attrs={'class': 'form-control'}),
            'post_9_correction': forms.NumberInput(attrs={'class': 'form-control'}),
            'post_10_correction': forms.NumberInput(attrs={'class': 'form-control'}),
            'post_11_correction': forms.NumberInput(attrs={'class': 'form-control'}),
            'post_12_correction': forms.NumberInput(attrs={'class': 'form-control'}),
            'post_13_correction': forms.NumberInput(attrs={'class': 'form-control'}),
            'post_14_correction': forms.NumberInput(attrs={'class': 'form-control'}),
            'post_15_correction': forms.NumberInput(attrs={'class': 'form-control'}),
            'post_16_correction': forms.NumberInput(attrs={'class': 'form-control'}),
            'post_17_correction': forms.NumberInput(attrs={'class': 'form-control'}),
            'post_18_correction': forms.NumberInput(attrs={'class': 'form-control'}),
            'post_19_correction': forms.NumberInput(attrs={'class': 'form-control'}),
            'post_20_correction': forms.NumberInput(attrs={'class': 'form-control'}),
        }
