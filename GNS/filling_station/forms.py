from crispy_forms.bootstrap import StrictButton
from django import forms
from .models import (Balloon, Truck, Trailer, RailwayTank, TTN, BalloonsLoadingBatch, BalloonsUnloadingBatch,
                     RailwayBatch, AutoGasBatch)
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout

USER_STATUS_LIST = [
    ('Создание паспорта баллона', 'Создание паспорта баллона'),
    ('Наполнение баллона сжиженным газом', 'Наполнение баллона сжиженным газом'),
    ('Погрузка пустого баллона в трал', 'Погрузка пустого баллона в трал'),
    ('Снятие RFID метки', 'Снятие RFID метки'),
    ('Установка новой RFID метки', 'Установка новой RFID метки'),
    ('Редактирование паспорта баллона', 'Редактирование паспорта баллона'),
    ('Покраска', 'Покраска'),
    ('Техническое освидетельствование', 'Техническое освидетельствование'),
    ('Выбраковка', 'Выбраковка'),
    ('Утечка газа', 'Утечка газа'),
    ('Опорожнение(слив) баллона', 'Опорожнение(слив) баллона'),
    ('Контрольное взвешивание', 'Контрольное взвешивание'),
]
GAS_TYPE_CHOICES = [
    ('Не выбран', 'Не выбран'),
    ('СПБТ', 'СПБТ'),
    ('ПБА', 'ПБА'),
]

BATCH_TYPE_CHOICES = [
    ('l', 'Приёмка'),
    ('u', 'Отгрузка'),
]


class GetBalloonsAmount(forms.Form):
    date = forms.CharField(max_length=10, label="Дата", widget=forms.DateInput(attrs={
        'class': 'form-control',
        'type': 'date'
    }))

    def clean_data(self):
        date_data = self.cleaned_data["date"]
        if date_data is None or len(date_data) != 10:
            raise forms.ValidationError("Поле не может быть пустым")
        return date_data


class BalloonForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.add_input(Submit('Сохранить', 'Сохранить', css_class='btn btn-success'))
        self.helper.form_method = 'POST'

    class Meta:
        model = Balloon
        fields = ['nfc_tag', 'serial_number', 'creation_date', 'size', 'netto', 'brutto', 'current_examination_date',
                  'next_examination_date', 'status', 'manufacturer', 'wall_thickness', 'filling_status',
                  'update_passport_required']
        widgets = {
            'nfc_tag': forms.TextInput(attrs={'class': 'form-control'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'creation_date': forms.DateInput(attrs={'type': 'date'}),
            'size': forms.NumberInput(attrs={'class': 'form-control'}),
            'netto': forms.NumberInput(attrs={'class': 'form-control'}),
            'brutto': forms.NumberInput(attrs={'class': 'form-control'}),
            'current_examination_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'next_examination_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'status': forms.Select(choices=USER_STATUS_LIST, attrs={'class': 'form-control'}),
            'manufacturer': forms.TextInput(attrs={'class': 'form-control'}),
            'wall_thickness': forms.NumberInput(attrs={'class': 'form-control'}),
            'filling_status': forms.CheckboxInput(attrs={'class': 'form-control'}),
            'update_passport_required': forms.CheckboxInput(attrs={'class': 'form-control'})
        }


class TruckForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.add_input(Submit('Сохранить', 'Сохранить', css_class='btn btn-success'))
        self.helper.form_method = 'POST'

    class Meta:
        model = Truck
        fields = ['car_brand', 'registration_number', 'type', 'capacity_cylinders',
                  'max_weight_of_transported_cylinders', 'max_mass_of_transported_gas', 'max_gas_volume', 'empty_weight',
                  'full_weight', 'is_on_station', 'entry_date', 'entry_time', 'departure_date', 'departure_time']
        widgets = {
            'car_brand': forms.TextInput(attrs={'class': 'form-control'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.TextInput(attrs={'class': 'form-control'}),
            'capacity_cylinders': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_weight_of_transported_cylinders': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_mass_of_transported_gas': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_gas_volume': forms.NumberInput(attrs={'class': 'form-control'}),
            'empty_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'full_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_on_station': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'entry_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'entry_time': forms.TimeInput(attrs={'type': 'time'}),
            'departure_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'departure_time': forms.TimeInput(attrs={'type': 'time'})
        }


class TrailerForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.add_input(Submit('Сохранить', 'Сохранить', css_class='btn btn-success'))
        self.helper.form_method = 'POST'

    class Meta:
        model = Trailer
        fields = ['truck', 'trailer_brand', 'registration_number', 'type', 'capacity_cylinders',
                  'max_weight_of_transported_cylinders', 'max_mass_of_transported_gas', 'max_gas_volume', 'empty_weight',
                  'full_weight', 'is_on_station', 'entry_date', 'entry_time', 'departure_date', 'departure_time']
        widgets = {
            'truck': forms.Select(attrs={'class': 'form-control'}),
            'trailer_brand': forms.TextInput(attrs={'class': 'form-control'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.TextInput(attrs={'class': 'form-control'}),
            'capacity_cylinders': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_weight_of_transported_cylinders': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_mass_of_transported_gas': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_gas_volume': forms.NumberInput(attrs={'class': 'form-control'}),
            'empty_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'full_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_on_station': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'entry_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'entry_time': forms.TimeInput(attrs={'type': 'time'}),
            'departure_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'departure_time': forms.TimeInput(attrs={'type': 'time'})
        }


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
        fields = ['registration_number', 'empty_weight', 'full_weight', 'gas_weight', 'gas_type', 'is_on_station',
                  'entry_date', 'entry_time', 'departure_date', 'departure_time']
        widgets = {
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'empty_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'full_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'gas_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'gas_type': forms.Select(choices=GAS_TYPE_CHOICES, attrs={'class': 'form-control'}),
            'is_on_station': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'entry_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'entry_time': forms.TimeInput(attrs={'type': 'time'}),
            'departure_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'departure_time': forms.TimeInput(attrs={'type': 'time'}),
        }


class TTNForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.add_input(Submit('Сохранить', 'Сохранить', css_class='btn btn-success'))
        self.helper.form_method = 'POST'

    class Meta:
        model = TTN
        fields = ['number', 'contract', 'shipper', 'consignee', 'gas_amount', 'gas_type', 'balloons_amount', 'date']
        widgets = {
            'number': forms.TextInput(attrs={'class': 'form-control'}),
            'contract': forms.TextInput(attrs={'class': 'form-control'}),
            'shipper': forms.TextInput(attrs={'class': 'form-control'}),
            'consignee': forms.TextInput(attrs={'class': 'form-control'}),
            'gas_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'gas_type': forms.Select(choices=GAS_TYPE_CHOICES, attrs={'class': 'form-control'}),
            'balloons_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        }


class BalloonsLoadingBatchForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.add_input(Submit('Сохранить', 'Сохранить', css_class='btn btn-success'))
        self.helper.form_method = 'POST'

    class Meta:
        model = BalloonsLoadingBatch
        fields = ['end_date', 'end_time', 'truck', 'trailer', 'reader_number',
                  'amount_of_rfid', 'amount_of_5_liters', 'amount_of_12_liters', 'amount_of_27_liters',
                  'amount_of_50_liters', 'gas_amount', 'is_active', 'ttn']
        widgets = {
            'end_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'truck': forms.Select(attrs={'class': 'form-control'}),
            'trailer': forms.Select(attrs={'class': 'form-control'}),
            'reader_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'amount_of_rfid': forms.NumberInput(attrs={'class': 'form-control'}),
            'amount_of_5_liters': forms.NumberInput(attrs={'class': 'form-control'}),
            'amount_of_12_liters': forms.NumberInput(attrs={'class': 'form-control'}),
            'amount_of_27_liters': forms.NumberInput(attrs={'class': 'form-control'}),
            'amount_of_50_liters': forms.NumberInput(attrs={'class': 'form-control'}),
            'gas_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ttn': forms.Select(attrs={'class': 'form-control'})
        }


class BalloonsUnloadingBatchForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.add_input(Submit('Сохранить', 'Сохранить', css_class='btn btn-success'))
        self.helper.form_method = 'POST'

    class Meta:
        model = BalloonsUnloadingBatch
        fields = ['end_date', 'end_time', 'truck', 'trailer', 'reader_number',
                  'amount_of_rfid', 'amount_of_5_liters', 'amount_of_12_liters', 'amount_of_27_liters',
                  'amount_of_50_liters', 'gas_amount', 'is_active', 'ttn']
        widgets = {
            'end_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'truck': forms.Select(attrs={'class': 'form-control'}),
            'trailer': forms.Select(attrs={'class': 'form-control'}),
            'reader_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'amount_of_rfid': forms.NumberInput(attrs={'class': 'form-control'}),
            'amount_of_5_liters': forms.NumberInput(attrs={'class': 'form-control'}),
            'amount_of_12_liters': forms.NumberInput(attrs={'class': 'form-control'}),
            'amount_of_27_liters': forms.NumberInput(attrs={'class': 'form-control'}),
            'amount_of_50_liters': forms.NumberInput(attrs={'class': 'form-control'}),
            'gas_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ttn': forms.Select(attrs={'class': 'form-control'})
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
        fields = ['end_date', 'end_time', 'gas_amount_spbt', 'gas_amount_pba', 'is_active', 'ttn']
        widgets = {
            'end_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'gas_amount_spbt': forms.NumberInput(attrs={'class': 'form-control'}),
            'gas_amount_pba': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ttn': forms.Select(attrs={'class': 'form-control'}),
        }


class AutoGasBatchForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.add_input(Submit('Сохранить', 'Сохранить', css_class='btn btn-success'))
        self.helper.form_method = 'POST'

    class Meta:
        model = AutoGasBatch
        fields = ['batch_type', 'end_date', 'end_time', 'truck', 'trailer', 'gas_amount', 'gas_type',
                  'scale_empty_weight', 'scale_full_weight', 'weight_gas_amount', 'is_active', 'ttn']
        widgets = {
            'batch_type': forms.Select(choices=BATCH_TYPE_CHOICES, attrs={'class': 'form-control'}),
            'end_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'truck': forms.Select(attrs={'class': 'form-control'}),
            'trailer': forms.Select(attrs={'class': 'form-control'}),
            'gas_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'gas_type': forms.Select(choices=GAS_TYPE_CHOICES, attrs={'class': 'form-control'}),
            'scale_empty_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'scale_full_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'weight_gas_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ttn': forms.Select(attrs={'class': 'form-control'})
        }
