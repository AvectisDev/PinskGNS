from django import forms
from django.conf import settings
from .models import RailwayTank, RailwayBatch
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit


class RailwayTankForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.add_input(Submit('Сохранить', 'Сохранить', css_class='btn btn-success'))
        self.helper.form_method = 'POST'

    class Meta:
        model = RailwayTank
        fields = [
            'registration_number',
            'empty_weight',
            'full_weight',
            'gas_weight',
            'gas_type',
            'is_on_station',
            'railway_ttn',
            'netto_weight_ttn',
            'entry_date',
            'entry_time',
            'departure_date',
            'departure_time'
        ]
        widgets = {
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'empty_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'full_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'gas_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'gas_type': forms.Select(choices=settings.GAS_TYPE_CHOICES, attrs={'class': 'form-control'}),
            'is_on_station': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'railway_ttn': forms.TextInput(attrs={'class': 'form-control'}),
            'netto_weight_ttn': forms.NumberInput(attrs={'class': 'form-control'}),
            'entry_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'entry_time': forms.TimeInput(attrs={'type': 'time'}),
            'departure_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'departure_time': forms.TimeInput(attrs={'type': 'time'}),
        }


class RailwayBatchForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.add_input(Submit('Сохранить', 'Сохранить', css_class='btn btn-success'))
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
