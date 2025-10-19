from django import forms
from django.conf import settings
from .models import RailwayTank, RailwayBatch, RailwayTankHistory
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit


class RailwayTankForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        show_actions = kwargs.pop('show_actions', True)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        if show_actions:
            self.helper.add_input(Submit('save', 'Сохранить', css_class='btn btn-success'))
            self.helper.add_input(Submit('cancel', 'Отмена', css_class='btn btn-secondary'))
        self.helper.form_method = 'POST'

    class Meta:
        model = RailwayTank
        fields = [
            'registration_number',
            'gas_type',
            'is_on_station',
        ]
        widgets = {
            'registration_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'gas_type': forms.Select(choices=settings.GAS_TYPE_CHOICES, attrs={'class': 'form-control'}),
            'is_on_station': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class RailwayTankHistoryForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-5'
        self.helper.field_class = 'col-lg-7'
        # Кнопки рендрим в общем шаблоне, здесь не добавляем
        # Настраиваем парсинг формата datetime-local
        dt_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M']
        if 'arrival_at' in self.fields:
            self.fields['arrival_at'].input_formats = dt_formats
        if 'departure_at' in self.fields:
            self.fields['departure_at'].input_formats = dt_formats

    class Meta:
        model = RailwayTankHistory
        fields = [
            'arrival_at',
            'departure_at',
            'full_weight',
            'empty_weight',
            'gas_weight',
            'railway_ttn',
            'netto_weight_ttn',
        ]
        widgets = {
            'arrival_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'departure_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'full_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'empty_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'gas_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'railway_ttn': forms.TextInput(attrs={'class': 'form-control'}),
            'netto_weight_ttn': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class RailwayBatchForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.add_input(Submit('save', 'Сохранить', css_class='btn btn-success'))
        self.helper.add_input(Submit('cancel', 'Отмена', css_class='btn btn-secondary'))
        self.helper.form_method = 'POST'

    class Meta:
        model = RailwayBatch
        fields = [
            'end_date',
            'gas_amount_spbt',
            'gas_amount_pba',
            'is_active'
        ]
        widgets = {
            'end_date': forms.DateTimeInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'gas_amount_spbt': forms.NumberInput(attrs={'class': 'form-control'}),
            'gas_amount_pba': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
