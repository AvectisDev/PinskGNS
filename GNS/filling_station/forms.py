from django import forms
from .models import Balloon


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


class UpdateBalloonPassport(forms.Form):
    nfc_tag = forms.CharField()
    serial_number = forms.CharField()
    creation_date = forms.DateField()
    size = forms.FloatField()
    netto = forms.FloatField()
    brutto = forms.FloatField()
    current_examination_date = forms.DateField()
    next_examination_date = forms.DateField()
    manufacturer = forms.CharField()
    wall_thickness = forms.FloatField()
    status = forms.CharField()

    #date = forms.CharField(max_length=10, label="Дата", widget=forms.TextInput(attrs={'placeholder': 'дд.мм.гггг'}))

    # def clean_data(self):
    #     date_data = self.cleaned_data["date"]
    #     if date_data is None or len(date_data) != 10:
    #         raise forms.ValidationError("Поле не может быть пустым")
    #     return date_data
