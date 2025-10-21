from django import forms
from django.utils.html import format_html
from django.conf import settings
from filling_station.models import BalloonsBatch
from autogas.models import AutoGasBatch, AutoGasBatchSettings
from .models import AutoTtn, RailwayTtn, BalloonTtn
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit


class BalloonTtnForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.add_input(Submit('save', 'Сохранить', css_class='btn btn-success'))
        self.helper.add_input(Submit('cancel', 'Отмена', css_class='btn btn-secondary'))
        self.helper.form_method = 'POST'

        self.fields['shipper'].empty_label = 'Выберите грузоотправителя'
        self.fields['carrier'].empty_label = 'Выберите перевозчика'
        self.fields['consignee'].empty_label = 'Выберите грузополучателя'
        self.fields['city'].empty_label = 'Выберите город'
        self.fields['loading_batch'].empty_label = 'Выберите партию приёмки'
        self.fields['unloading_batch'].empty_label = 'Выберите партию отгрузки'

        # Добавляем ID для JS, но оставляем поле редактируемым
        self.fields['number'].widget.attrs.update({
            'id': 'id_ttn_number',
            'class': 'form-control',
            'placeholder': 'Номер заполнится автоматически или введите вручную'
        })

        # Оптимизированные запросы для партий с select_related
        self.fields['loading_batch'].queryset = BalloonsBatch.objects.filter(batch_type='l').select_related('truck')
        self.fields['unloading_batch'].queryset = BalloonsBatch.objects.filter(batch_type='u').select_related('truck')

        self.fields['loading_batch'].label_from_instance = self.format_batch_choice
        self.fields['unloading_batch'].label_from_instance = self.format_batch_choice

        # Добавляем data-атрибуты для выпадающих списков
        self.fields['loading_batch'].widget.attrs['data-ttn-field'] = 'id_ttn_number'
        self.fields['unloading_batch'].widget.attrs['data-ttn-field'] = 'id_ttn_number'

    def format_batch_choice(self, obj):
        """Форматирует отображение партии в выпадающем списке"""
        if obj.batch_type == 'l' or 'u':
            batch_type = 'Приёмка'
        else:
            batch_type = 'Отгрузка'

        truck_number = obj.truck.registration_number if obj.truck else '---'
        ttn_number = obj.ttn if obj.ttn else '---'

        return format_html(
            '<span data-ttn="{}">{} №{} | Автомобиль: {} | ТТН: {}</span>',
            ttn_number,
            batch_type,
            obj.id,
            truck_number,
            ttn_number
        )

    class Meta:
        model = BalloonTtn
        fields = [
            'number',
            'contract',
            'shipper',
            'carrier',
            'consignee',
            'city',
            'loading_batch',
            'unloading_batch'
        ]
        widgets = {
            'number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Номер заполнится автоматически'
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
            'city': forms.Select(attrs={
                'class': 'form-control',
            }),
            'loading_batch': forms.Select(attrs={
                'class': 'form-control',
            }),
            'unloading_batch': forms.Select(attrs={
                'class': 'form-control',
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        loading_batch = cleaned_data.get('loading_batch')
        unloading_batch = cleaned_data.get('unloading_batch')

        if loading_batch and unloading_batch:
            raise forms.ValidationError("Выберите только партию приёмки ИЛИ партию отгрузки, не обе одновременно")

        return cleaned_data


class AutoTtnForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.add_input(Submit('save', 'Сохранить', css_class='btn btn-success'))
        self.helper.add_input(Submit('cancel', 'Отмена', css_class='btn btn-secondary'))
        self.helper.form_method = 'POST'

        self.fields['shipper'].empty_label = 'Выберите грузоотправителя'
        self.fields['carrier'].empty_label = 'Выберите перевозчика'
        self.fields['consignee'].empty_label = 'Выберите грузополучателя'
        self.fields['city'].empty_label = 'Выберите город'
        self.fields['batch'].empty_label = 'Выберите партию'

        # Оптимизированные запросы для партии с select_related
        self.fields['batch'].queryset = AutoGasBatch.objects.select_related('truck')

        self.fields['batch'].label_from_instance = self.format_batch_choice

        # Добавляем data-атрибуты для выпадающих списков
        self.fields['batch'].widget.attrs['data-ttn-field'] = 'id_ttn_number'

    def format_batch_choice(self, obj):
        """Форматирует отображение партии в выпадающем списке"""

        return format_html(
            '<span>{} №{} | Автомобиль: {}</span>',
            'Приёмка' if obj.batch_type == 'l' else 'Отгрузка',
            obj.id,
            obj.truck.registration_number if obj.truck else '---'
        )

    class Meta:
        model = AutoTtn
        fields = [
            'number',
            'contract',
            'shipper',
            'carrier',
            'consignee',
            'city',
            'batch'
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
            'city': forms.Select(attrs={
                'class': 'form-control',
            }),
            'batch': forms.Select(attrs={
                'class': 'form-control',
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
                settings = AutoGasBatchSettings.objects.first()

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


class RailwayTtnForm(forms.ModelForm):
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
        model = RailwayTtn
        fields = [
            'number',
            'railway_ttn',
            'contract',
            'shipper',
            'carrier',
            'consignee',
            'gas_type'
        ]
        widgets = {
            'number': forms.TextInput(attrs={'class': 'form-control'}),
            'railway_ttn': forms.TextInput(attrs={
                'class': 'form-control',
                'onchange': 'this.form.submit()'  # Авто сохранение при изменении
            }),
            'contract': forms.TextInput(attrs={'class': 'form-control'}),
            'gas_type': forms.Select(choices=settings.GAS_TYPE_CHOICES, attrs={'class': 'form-control'}),
            'shipper': forms.Select(attrs={'class': 'form-control'}),
            'carrier': forms.Select(attrs={'class': 'form-control'}),
            'consignee': forms.Select(attrs={'class': 'form-control'}),
        }
