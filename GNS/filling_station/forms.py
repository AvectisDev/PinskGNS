from crispy_forms.bootstrap import StrictButton
from django import forms
from django.utils import timezone
from filling_station import models
from .models import GAS_TYPE_CHOICES, BATCH_TYPE_CHOICES, BALLOON_SIZE_CHOICES
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
        model = models.CarouselSettings
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
        model = models.Balloon
        fields = ['nfc_tag', 'serial_number', 'creation_date', 'size', 'netto', 'brutto', 'current_examination_date',
                  'next_examination_date', 'diagnostic_date', 'working_pressure', 'status', 'manufacturer',
                  'wall_thickness', 'filling_status', 'update_passport_required']
        widgets = {
            'nfc_tag': forms.TextInput(attrs={'class': 'form-control'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'creation_date': forms.DateInput(attrs={'type': 'date'}),
            'size': forms.Select(choices=BALLOON_SIZE_CHOICES, attrs={'class': 'form-control'}),
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
        self.helper.add_input(Submit('Сохранить', 'Сохранить', css_class='btn btn-success'))
        self.helper.form_method = 'POST'

    class Meta:
        model = models.Truck
        fields = ['car_brand', 'registration_number', 'type', 'capacity_cylinders',
                  'max_weight_of_transported_cylinders', 'max_mass_of_transported_gas', 'max_gas_volume',
                  'empty_weight',
                  'full_weight', 'is_on_station', 'entry_date', 'entry_time', 'departure_date', 'departure_time']
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
        model = models.Trailer
        fields = ['truck', 'trailer_brand', 'registration_number', 'type', 'capacity_cylinders',
                  'max_weight_of_transported_cylinders', 'max_mass_of_transported_gas', 'max_gas_volume',
                  'empty_weight',
                  'full_weight', 'is_on_station', 'entry_date', 'entry_time', 'departure_date', 'departure_time']
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
            'entry_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'entry_time': forms.TimeInput(attrs={'type': 'time'}),
            'departure_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'departure_time': forms.TimeInput(attrs={'type': 'time'})
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

        self.fields['shipper'].empty_label = 'Выберите грузоотправителя'
        self.fields['carrier'].empty_label = 'Выберите перевозчика'
        self.fields['consignee'].empty_label = 'Выберите грузополучателя'
        self.fields['loading_batch'].empty_label = 'Выберите партию приёмки'
        self.fields['unloading_batch'].empty_label = 'Выберите партию отгрузки'

        self.fields['loading_batch'].label_from_instance = self.format_batch_choice
        self.fields['unloading_batch'].label_from_instance = self.format_batch_choice

    def format_batch_choice(self, obj):
        """Форматирует отображение партии в выпадающем списке"""
        if isinstance(obj, models.BalloonsLoadingBatch):
            batch_type = 'Приёмка'
        else:
            batch_type = 'Отгрузка'

        truck_number = obj.truck.registration_number if obj.truck else '---'
        ttn_number = obj.ttn if obj.ttn else '---'

        return f"{batch_type} №{obj.id} | Автомобиль: {truck_number} | ТТН: {ttn_number}"

    class Meta:
        model = models.NewTTN
        fields = [
            'number',
            'contract',
            'shipper',
            'carrier',
            'consignee',
            'loading_batch',
            'unloading_batch',
            'date'
        ]
        widgets = {
            'number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите номер ТТН'
            }),
            'contract': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Номер договора'
            }),
            'shipper': forms.Select(attrs={
                'class': 'form-control',
            }),
            'carrier': forms.Select(attrs={
                'class': 'form-control',
            }),
            'consignee': forms.Select(attrs={
                'class': 'form-control',
            }),
            'loading_batch': forms.Select(attrs={
                'class': 'form-control',
            }),
            'unloading_batch': forms.Select(attrs={
                'class': 'form-control',
            }),
            'date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'placeholder': 'Дата формирования'
            }),
        }
        labels = {
            'loading_batch': 'Партия приёмки',
            'unloading_batch': 'Партия отгрузки'
        }

    def clean(self):
        cleaned_data = super().clean()
        loading_batch = cleaned_data.get('loading_batch')
        unloading_batch = cleaned_data.get('unloading_batch')

        if loading_batch and unloading_batch:
            raise forms.ValidationError("Выберите только партию приёмки ИЛИ партию отгрузки, не обе одновременно")

        # Автоматически заполняем номер ТТН из выбранной партии
        if loading_batch:
            cleaned_data['number'] = loading_batch.ttn
        elif unloading_batch:
            cleaned_data['number'] = unloading_batch.ttn

        return cleaned_data


class BalloonsLoadingBatchForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.add_input(Submit('Сохранить', 'Сохранить', css_class='btn btn-success'))
        self.helper.form_method = 'POST'

        self.fields['truck'].empty_label = 'Выберите автомобиль'
        self.fields['trailer'].empty_label = 'Выберите прицеп'

    class Meta:
        model = models.BalloonsLoadingBatch
        fields = [
            'end_date',
            'end_time',
            'truck',
            'trailer',
            'reader_number',
            'amount_of_rfid',
            'amount_of_5_liters',
            'amount_of_12_liters',
            'amount_of_27_liters',
            'amount_of_50_liters',
            'gas_amount',
            'is_active',
            'ttn',
            'amount_of_ttn'
        ]
        widgets = {
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'end_time': forms.TimeInput(attrs={
                'type': 'time',
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
            'ttn': 'Номер ТТН'
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

        self.fields['truck'].empty_label = 'Выберите автомобиль'
        self.fields['trailer'].empty_label = 'Выберите прицеп'

    class Meta:
        model = models.BalloonsUnloadingBatch
        fields = [
            'end_date',
            'end_time',
            'truck',
            'trailer',
            'reader_number',
            'amount_of_rfid',
            'amount_of_5_liters',
            'amount_of_12_liters',
            'amount_of_27_liters',
            'amount_of_50_liters',
            'gas_amount',
            'is_active',
            'ttn',
            'amount_of_ttn'
        ]
        widgets = {
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'end_time': forms.TimeInput(attrs={
                'type': 'time',
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
            'ttn': 'Номер ТТН'
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

        self.fields['truck'].empty_label = 'Выберите автомобиль'
        self.fields['trailer'].empty_label = 'Выберите прицеп'

        self.fields['end_date'].widget.attrs.update({'class': 'form-control'})
        self.fields['end_time'].widget.attrs.update({'class': 'form-control'})

    class Meta:
        model = models.AutoGasBatch
        fields = [
            'batch_type',
            'end_date',
            'end_time',
            'truck',
            'trailer',
            'gas_amount',
            'gas_type',
            'scale_empty_weight',
            'scale_full_weight',
            'weight_gas_amount',
            'is_active'
        ]
        widgets = {
            'batch_type': forms.Select(attrs={
                'class': 'form-control',
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'end_time': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
            'truck': forms.Select(attrs={
                'class': 'form-control',
            }),
            'trailer': forms.Select(attrs={
                'class': 'form-control',
            }),
            'gas_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите количество газа по массомеру',
                'step': '0.01'
            }),
            'gas_type': forms.Select(attrs={
                'class': 'form-control',
            }),
            'scale_empty_weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Вес пустого транспорта',
                'step': '0.01'
            }),
            'scale_full_weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Вес груженого транспорта',
                'step': '0.01'
            }),
            'weight_gas_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Количество газа по весам',
                'step': '0.01'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            })
        }
        labels = {
            'weight_gas_amount': 'Количество газа (по весам)',
            'gas_amount': 'Количество газа (по массомеру)'
        }

    def clean(self):
        cleaned_data = super().clean()

        # Проверка, что дата окончания не раньше даты начала
        if self.instance.pk and cleaned_data.get('end_date'):
            if cleaned_data['end_date'] < self.instance.begin_date:
                raise forms.ValidationError(
                    "Дата окончания не может быть раньше даты начала"
                )

        # Проверка весовых показателей
        scale_empty = cleaned_data.get('scale_empty_weight')
        scale_full = cleaned_data.get('scale_full_weight')
        weight_gas = cleaned_data.get('weight_gas_amount')

        if scale_empty and scale_full:
            if scale_full <= scale_empty:
                raise forms.ValidationError(
                    "Вес груженого транспорта должен быть больше веса пустого"
                )

            calculated_gas = scale_full - scale_empty
            if weight_gas and abs(weight_gas - calculated_gas) > 0.1:
                raise forms.ValidationError(
                    f"Расчетное количество газа ({calculated_gas:.2f}) не совпадает с введенным ({weight_gas:.2f})"
                )

        return cleaned_data


class AutoTtnForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.add_input(Submit('Сохранить', 'Сохранить', css_class='btn btn-success'))
        self.helper.form_method = 'POST'

        self.fields['shipper'].empty_label = 'Выберите грузоотправителя'
        self.fields['carrier'].empty_label = 'Выберите перевозчика'
        self.fields['consignee'].empty_label = 'Выберите грузополучателя'
        self.fields['batch'].empty_label = 'Выберите номер партии'

    class Meta:
        model = models.AutoTtn
        fields = [
            'number',
            'contract',
            'shipper',
            'carrier',
            'consignee',
            'batch',
            'total_gas_amount',
            'gas_type',
            'date'
        ]
        widgets = {
            'number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите номер ТТН'
            }),
            'contract': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Номер договора'
            }),
            'shipper': forms.Select(attrs={
                'class': 'form-control',
            }),
            'carrier': forms.Select(attrs={
                'class': 'form-control',
            }),
            'consignee': forms.Select(attrs={
                'class': 'form-control',
            }),
            'batch': forms.Select(attrs={
                'class': 'form-control',
            }),
            'total_gas_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Количество газа',
                'step': '0.01'
            }),
            'gas_type': forms.Select(attrs={
                'class': 'form-control',
            }),
            'date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'placeholder': 'Дата формирования накладной'
            }),
        }
        labels = {
            'source_gas_amount': 'Источник данных о весе',
            'gas_type': 'Тип газа'
        }

        def clean(self):
            cleaned_data = super().clean()
            batch = cleaned_data.get('batch')

            if batch:
                settings = models.AutoGasBatchSettings.objects.first()

                # Проверка наличия данных о газе в партии
                if settings and settings.weight_source == 'f' and not batch.gas_amount:
                    raise forms.ValidationError(
                        "В выбранной партии не указано количество газа по расходомеру"
                    )
                elif settings and settings.weight_source == 's' and not batch.weight_gas_amount:
                    raise forms.ValidationError(
                        "В выбранной партии не указано количество газа по весам"
                    )

                # Проверка наличия типа газа в партии
                if not batch.gas_type or batch.gas_type == 'Не выбран':
                    raise forms.ValidationError(
                        "В выбранной партии не указан тип газа"
                    )

            return cleaned_data


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
        model = models.RailwayTank
        fields = ['registration_number', 'empty_weight', 'full_weight', 'gas_weight', 'gas_type', 'is_on_station',
                  'railway_ttn', 'netto_weight_ttn', 'entry_date', 'entry_time', 'departure_date', 'departure_time']
        widgets = {
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'empty_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'full_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'gas_weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'gas_type': forms.Select(choices=GAS_TYPE_CHOICES, attrs={'class': 'form-control'}),
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
        model = models.RailwayBatch
        fields = ['end_date', 'gas_amount_spbt', 'gas_amount_pba', 'is_active']
        widgets = {
            'end_date': forms.DateTimeInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'gas_amount_spbt': forms.NumberInput(attrs={'class': 'form-control'}),
            'gas_amount_pba': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }


class RailwayTtnForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.add_input(Submit('Сохранить', 'Сохранить', css_class='btn btn-success'))
        self.helper.form_method = 'POST'

    class Meta:
        model = models.RailwayTtn
        fields = [
            'number',
            'railway_ttn',
            'contract',
            'shipper',
            'carrier',
            'consignee',
            'gas_type',
            'date'
        ]
        widgets = {
            'number': forms.TextInput(attrs={'class': 'form-control'}),
            'railway_ttn': forms.TextInput(attrs={
                'class': 'form-control',
                'onchange': 'this.form.submit()'  # Авто сохранение при изменении
            }),
            'contract': forms.TextInput(attrs={'class': 'form-control'}),
            'gas_type': forms.Select(choices=GAS_TYPE_CHOICES, attrs={'class': 'form-control'}),
            'date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'shipper': forms.Select(attrs={'class': 'form-control'}),
            'carrier': forms.Select(attrs={'class': 'form-control'}),
            'consignee': forms.Select(attrs={'class': 'form-control'}),
        }
