from django import forms
from .models import AutoGasBatch
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit


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
        model = AutoGasBatch
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
