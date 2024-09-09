from django import forms
from .models import (Balloon, Truck, Trailer, RailwayTanks, TTN, BalloonsLoadingBatch, BalloonsUnloadingBatch,
                     RailwayLoadingBatch, GasLoadingBatch, GasUnloadingBatch)


class Process(forms.Form):
    truck_number = forms.CharField(max_length=15, label="Госномер автомобиля", widget=forms.TextInput(attrs={'placeholder': '1234 AA-1'}))
    phone_number = forms.CharField(max_length=15, label="Номер телефона", widget=forms.TextInput(attrs={'placeholder': '375291112233'}))
    company = forms.CharField(max_length=200, label="Компания")

    def clean_phone_number(self):
        phone_number_data = self.cleaned_data["phone_number"]
        if not phone_number_data.isdigit():
            raise forms.ValidationError("Номер телефона должен состоять только из цифр")
        return phone_number_data


class GetBalloonsAmount(forms.Form):
    date = forms.CharField(max_length=10, label="Дата", widget=forms.TextInput(attrs={'placeholder': 'дд.мм.гггг'}))

    def clean_data(self):
        date_data = self.cleaned_data["date"]
        if date_data is None or len(date_data) != 10:
            raise forms.ValidationError("Поле не может быть пустым")
        return date_data


class BalloonPassportForm(forms.ModelForm):
    class Meta:
        model = Balloon
        fields = ['nfc_tag', 'serial_number', 'creation_date', 'size', 'netto', 'brutto',
                  'current_examination_date', 'next_examination_date', 'manufacturer', 'wall_thickness', 'status']
        widgets = {
            'nfc_tag': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'creation_date': forms.SelectDateWidget(attrs={'class': 'form-control'}),
            'size': forms.NumberInput(attrs={'class': 'form-control'}),
            'netto': forms.NumberInput(attrs={'class': 'form-control'}),
            'brutto': forms.NumberInput(attrs={'class': 'form-control'}),
            'current_examination_date': forms.SelectDateWidget(attrs={'class': 'form-control'}),
            'next_examination_date': forms.SelectDateWidget(attrs={'class': 'form-control'}),
            'manufacturer': forms.TextInput(attrs={'class': 'form-control'}),
            'wall_thickness': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.TextInput(attrs={'class': 'form-control'})
        }


class TruckForm(forms.ModelForm):
    class Meta:
        model = Truck
        fields = ['car_brand', 'registration_number', 'type', 'max_capacity_cylinders_by_type',
                  'max_weight_of_transported_cylinders', 'max_mass_of_transported_gas', 'empty_weight',
                  'full_weight', 'is_on_station', 'entry_date', 'entry_time', 'departure_date', 'departure_time']
        widgets = {
            'car_brand': forms.TextInput(attrs={'class': 'form-control'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.DateInput(attrs={'class': 'form-control'}),
            'max_capacity_cylinders_by_type': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_weight_of_transported_cylinders': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_mass_of_transported_gas': forms.NumberInput(attrs={'class': 'form-control'}),
            'empty_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'full_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_on_station': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'entry_date': forms.SelectDateWidget(attrs={'class': 'form-control'}),
            'entry_time': forms.TimeInput(attrs={'class': 'form-control'}),
            'departure_date': forms.SelectDateWidget(attrs={'class': 'form-control'}),
            'departure_time': forms.TimeInput(attrs={'class': 'form-control'})
        }


class TrailerForm(forms.ModelForm):
    class Meta:
        model = Trailer
        fields = ['trailer_brand', 'registration_number', 'type', 'max_capacity_cylinders_by_type',
                  'max_weight_of_transported_cylinders', 'max_mass_of_transported_gas', 'empty_weight',
                  'full_weight', 'is_on_station']
        widgets = {
            'trailer_brand': forms.TextInput(attrs={'class': 'form-control'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.DateInput(attrs={'class': 'form-control'}),
            'max_capacity_cylinders_by_type': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_weight_of_transported_cylinders': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_mass_of_transported_gas': forms.NumberInput(attrs={'class': 'form-control'}),
            'empty_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'full_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_on_station': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class RailwayTanksForm(forms.ModelForm):
    class Meta:
        model = RailwayTanks
        fields = ['number', 'empty_weight', 'full_weight', 'is_on_station', 'entry_date', 'entry_time',
                  'departure_date', 'departure_time']
        widgets = {
            'number': forms.TextInput(attrs={'class': 'form-control'}),
            'empty_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'full_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_on_station': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'entry_date': forms.SelectDateWidget(attrs={'class': 'form-control'}),
            'entry_time': forms.TimeInput(attrs={'class': 'form-control'}),
            'departure_date': forms.SelectDateWidget(attrs={'class': 'form-control'}),
            'departure_time': forms.TimeInput(attrs={'class': 'form-control'})
        }


class TTNForm(forms.ModelForm):
    class Meta:
        model = TTN
        fields = ['number', 'contract', 'name_of_supplier', 'gas_amount', 'balloons_amount', 'date']
        widgets = {
            'number': forms.TextInput(attrs={'class': 'form-control'}),
            'contract': forms.TextInput(attrs={'class': 'form-control'}),
            'name_of_supplier': forms.TextInput(attrs={'class': 'form-control'}),
            'gas_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'balloons_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'date': forms.SelectDateWidget(attrs={'class': 'form-control'}),
        }


class BalloonsLoadingBatchForm(forms.ModelForm):
    class Meta:
        model = BalloonsLoadingBatch
        fields = ['end_date', 'end_time', 'truck', 'trailer',
                  'amount_of_rfid', 'amount_of_5_liters', 'amount_of_20_liters', 'amount_of_50_liters', 'gas_amount',
                  'is_active', 'ttn']
        widgets = {
            'end_date': forms.SelectDateWidget(attrs={'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control'}),
            'truck': forms.Select(attrs={'class': 'form-control'}),
            'trailer': forms.Select(attrs={'class': 'form-control'}),
            'amount_of_rfid': forms.NumberInput(attrs={'class': 'form-control'}),
            'amount_of_5_liters': forms.NumberInput(attrs={'class': 'form-control'}),
            'amount_of_20_liters': forms.NumberInput(attrs={'class': 'form-control'}),
            'amount_of_50_liters': forms.NumberInput(attrs={'class': 'form-control'}),
            'gas_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ttn': forms.Select(attrs={'class': 'form-control'})
        }


class BalloonsUnloadingBatchForm(forms.ModelForm):
    class Meta:
        model = BalloonsUnloadingBatch
        fields = ['end_date', 'end_time', 'truck', 'trailer',
                  'amount_of_rfid', 'amount_of_5_liters', 'amount_of_20_liters', 'amount_of_50_liters', 'gas_amount',
                  'is_active', 'ttn']
        widgets = {
            'end_date': forms.SelectDateWidget(attrs={'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control'}),
            'truck': forms.Select(attrs={'class': 'form-control'}),
            'trailer': forms.Select(attrs={'class': 'form-control'}),
            'amount_of_rfid': forms.NumberInput(attrs={'class': 'form-control'}),
            'amount_of_5_liters': forms.NumberInput(attrs={'class': 'form-control'}),
            'amount_of_20_liters': forms.NumberInput(attrs={'class': 'form-control'}),
            'amount_of_50_liters': forms.NumberInput(attrs={'class': 'form-control'}),
            'gas_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ttn': forms.Select(attrs={'class': 'form-control'})
        }


class RailwayLoadingBatchForm(forms.ModelForm):
    class Meta:
        model = BalloonsUnloadingBatch
        fields = ['end_date', 'end_time', 'gas_amount',
                  'is_active', 'ttn']
        widgets = {
            'end_date': forms.SelectDateWidget(attrs={'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control'}),
            'gas_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ttn': forms.Select(attrs={'class': 'form-control'}),
        }


class GasLoadingBatchForm(forms.ModelForm):
    class Meta:
        model = GasLoadingBatch
        fields = ['end_date', 'end_time', 'truck', 'trailer', 'gas_amount', 'is_active', 'ttn']
        widgets = {
            'end_date': forms.SelectDateWidget(attrs={'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control'}),
            'truck': forms.Select(attrs={'class': 'form-control'}),
            'trailer': forms.Select(attrs={'class': 'form-control'}),
            'gas_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ttn': forms.Select(attrs={'class': 'form-control'})
        }


class GasUnloadingBatchForm(forms.ModelForm):
    class Meta:
        model = GasUnloadingBatch
        fields = ['end_date', 'end_time', 'truck', 'trailer', 'gas_amount', 'is_active', 'ttn']
        widgets = {
            'end_date': forms.SelectDateWidget(attrs={'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control'}),
            'truck': forms.Select(attrs={'class': 'form-control'}),
            'trailer': forms.Select(attrs={'class': 'form-control'}),
            'gas_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ttn': forms.Select(attrs={'class': 'form-control'})
        }

