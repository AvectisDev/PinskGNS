from django import forms
from django.utils import timezone
from django.conf import settings
from .models import Balloon, Truck, Trailer, BalloonsBatch
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

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


class GetBalloonsAmount(forms.Form):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.form_method = 'POST'


class BalloonForm(forms.ModelForm):

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
        model = Balloon
        exclude = ['user', 'change_date']
        widgets = {
            'nfc_tag': forms.TextInput(attrs={'class': 'form-control'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'creation_date': forms.DateInput(attrs={'type': 'date'}),
            'size': forms.Select(choices=settings.BALLOON_SIZE_CHOICES, attrs={'class': 'form-control'}),
            'netto': forms.NumberInput(attrs={'class': 'form-control'}),
            'brutto': forms.NumberInput(attrs={'class': 'form-control'}),
            'current_examination_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'next_examination_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'diagnostic_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'working_pressure': forms.NumberInput(attrs={'class': 'form-control'}),
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
        self.helper.add_input(Submit('save', 'Сохранить', css_class='btn btn-success'))
        self.helper.add_input(Submit('cancel', 'Отмена', css_class='btn btn-secondary'))
        self.helper.form_method = 'POST'

    class Meta:
        model = Truck
        fields = '__all__'
        widgets = {
            'car_brand': forms.TextInput(attrs={'class': 'form-control'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-control'}),
            'capacity_cylinders': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_weight_of_transported_cylinders': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_mass_of_transported_gas': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_gas_volume': forms.NumberInput(attrs={'class': 'form-control'}),
            'empty_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'full_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_on_station': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'entry_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={
                'type': 'datetime-local',
                'class': 'form-control'
                }),
            'departure_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={
                'type': 'datetime-local',
                'class': 'form-control'
                })
        }


class TrailerForm(forms.ModelForm):
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
            'entry_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M',attrs={
                'type': 'datetime-local',
                'class': 'form-control'
                }),
            'departure_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={
                'type': 'datetime-local',
                'class': 'form-control'
                })
        }


class BalloonsBatchForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.add_input(Submit('save', 'Сохранить', css_class='btn btn-success'))
        self.helper.add_input(Submit('cancel', 'Отмена', css_class='btn btn-secondary'))
        self.helper.form_method = 'POST'

        self.fields['truck'].empty_label = 'Выберите автомобиль'
        self.fields['trailer'].empty_label = 'Выберите прицеп'
        # Скрыть batch_type
        self.fields['batch_type'].widget = forms.HiddenInput()

    class Meta:
        model = BalloonsBatch
        exclude = ['user', 'balloon_list']
        widgets = {
            'batch_type': forms.HiddenInput(),
            'completed_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'truck': forms.Select(attrs={
                'class': 'form-control'
            }),
            'trailer': forms.Select(attrs={
                'class': 'form-control'
            }),
            'reader_number': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите номер считывателя'
            }),
            'amount_of_rfid': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Количество по RFID'
            }),
            'amount_of_5_liters': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0'
            }),
            'amount_of_12_liters': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0'
            }),
            'amount_of_27_liters': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0'
            }),
            'amount_of_50_liters': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0'
            }),
            'gas_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Количество газа',
                'step': '0.01'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'ttn': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Номер ТТН'
            }),
            'amount_of_ttn': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Количество по ТТН'
            })
        }
        labels = {
            'amount_of_ttn': 'Количество баллонов по ТТН',
            'ttn': 'Номер ТТН',
            'batch_type': 'Тип партии'
        }
