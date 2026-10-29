from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from transport.form_choices import configure_driver_field, configure_truck_field
from transport.models import Truck, Trailer
from transport.registration import (
    TRAILER_INPUT_HELP,
    TRUCK_INPUT_HELP,
    validate_trailer_input,
    validate_truck_input,
)


class TruckForm(forms.ModelForm):
    """ModelForm грузовика для создания и редактирования."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-5 text-lg-end'
        self.helper.field_class = 'col-lg-3'
        self.helper.add_input(Submit('save', 'Сохранить', css_class='btn btn-success'))
        self.helper.add_input(Submit('cancel', 'Отмена', css_class='btn btn-secondary', formnovalidate='formnovalidate'))
        self.helper.form_method = 'POST'

        reg_field = self.fields['registration_number']
        reg_field.help_text = TRUCK_INPUT_HELP
        reg_field.widget.attrs.setdefault('placeholder', 'AH 0193-1')

        configure_driver_field(self.fields['driver'], truck=self.instance)

    def clean_registration_number(self):
        return validate_truck_input(self.cleaned_data.get('registration_number', ''))

    class Meta:
        model = Truck
        fields = '__all__'
        widgets = {
            'car_brand': forms.TextInput(attrs={'class': 'form-control'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-control'}),
            'driver': forms.Select(attrs={'class': 'form-control'}),
            'capacity_cylinders': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_weight_of_transported_cylinders': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_mass_of_transported_gas': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_gas_volume': forms.NumberInput(attrs={'class': 'form-control'}),
            'empty_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'full_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_on_station': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'entry_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={
                'type': 'datetime-local',
                'class': 'form-control'
                }),
            'departure_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={
                'type': 'datetime-local',
                'class': 'form-control'
                }),
            'photo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class TrailerForm(forms.ModelForm):
    """ModelForm прицепа для создания и редактирования."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-5 text-lg-end'
        self.helper.field_class = 'col-lg-5'
        self.helper.add_input(Submit('save', 'Сохранить', css_class='btn btn-success'))
        self.helper.add_input(Submit('cancel', 'Отмена', css_class='btn btn-secondary', formnovalidate='formnovalidate'))
        self.helper.form_method = 'POST'

        self.fields['truck'].empty_label = 'Выберите автомобиль'
        configure_truck_field(self.fields['truck'])

        reg_field = self.fields['registration_number']
        reg_field.help_text = TRAILER_INPUT_HELP
        reg_field.widget.attrs.setdefault('placeholder', 'A 3779B-1')

    def clean_registration_number(self):
        return validate_trailer_input(self.cleaned_data.get('registration_number', ''))

    class Meta:
        model = Trailer
        fields = '__all__'
        widgets = {
            'truck': forms.Select(attrs={'class': 'form-control'}),
            'trailer_brand': forms.TextInput(attrs={'class': 'form-control'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-control'}),
            'capacity_cylinders': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_weight_of_transported_cylinders': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_mass_of_transported_gas': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_gas_volume': forms.NumberInput(attrs={'class': 'form-control'}),
            'empty_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'full_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_on_station': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'entry_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M',attrs={
                'type': 'datetime-local',
                'class': 'form-control'
                }),
            'departure_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={
                'type': 'datetime-local',
                'class': 'form-control'
                })
        }
