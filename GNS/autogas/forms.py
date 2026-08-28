from django import forms
from filling_station.form_choices import configure_trailer_field, configure_truck_field
from .models import AutoGasBatch
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit


class AutoGasBatchForm(forms.ModelForm):
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
        self.fields['trailer'].empty_label = 'Выберите прицеп'
        configure_truck_field(self.fields['truck'])
        configure_trailer_field(self.fields['trailer'])

    class Meta:
        model = AutoGasBatch
        exclude = ['user']
        widgets = {
            'batch_type': forms.Select(attrs={
                'class': 'form-control',
            }),
            'completed_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={
                'type': 'datetime-local',
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
                'step': '0.1'
            }),
            'gas_type': forms.Select(attrs={
                'class': 'form-control',
            }),
            'scale_empty_weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Вес пустого транспорта',
                'step': '0.1'
            }),
            'scale_full_weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Вес груженого транспорта',
                'step': '0.1'
            }),
            'weight_gas_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Количество газа по весам',
                'step': '0.1'
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

        completed_at = cleaned_data.get('completed_at')
        begin_at = self.instance.begin_at if self.instance.pk else None
        if completed_at and begin_at and completed_at < begin_at:
            self.add_error(
                'completed_at',
                'Дата окончания не может быть раньше даты начала',
            )

        if cleaned_data.get('is_active'):
            active_qs = AutoGasBatch.objects.filter(is_active=True)
            if self.instance.pk:
                active_qs = active_qs.exclude(pk=self.instance.pk)
            if active_qs.exists():
                self.add_error('is_active', 'Уже есть активная партия')

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
