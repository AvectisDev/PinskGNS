"""Формы Django для работы с баллонами, транспортом и партиями на ГНС."""

from django import forms
from django.utils import timezone
from django.conf import settings
from .models import Balloon, BalloonUserStatus, BalloonsBatch
from transport.form_choices import configure_trailer_field, configure_truck_field
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit


class GetBalloonsAmount(forms.Form):
    """Форма выбора периода для подсчёта количества баллонов в статистике."""

    start_date = forms.DateField(
        label="Начальная дата",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=timezone.localdate()
    )
    end_date = forms.DateField(
        label="Конечная дата",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=timezone.localdate()
    )

    def __init__(self, *args, **kwargs):
        """Инициализирует форму и настраивает горизонтальный layout crispy-forms."""
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        self.helper.form_method = 'POST'


class BalloonForm(forms.ModelForm):
    """ModelForm паспорта баллона для создания и редактирования в веб-интерфейсе."""

    def __init__(self, *args, **kwargs):
        """Инициализирует форму паспорта и кнопки сохранения/отмены через crispy-forms."""
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-5 text-lg-end'
        self.helper.field_class = 'col-lg-3'
        self.helper.add_input(Submit('save', 'Сохранить', css_class='btn btn-success'))
        self.helper.add_input(Submit('cancel', 'Отмена', css_class='btn btn-secondary', formnovalidate='formnovalidate'))
        self.helper.form_method = 'POST'
        status_choices = [('', '---------')] + BalloonUserStatus.active_choices()
        self.fields['status'].choices = status_choices
        self.fields['status'].widget = forms.Select(
            choices=status_choices,
            attrs={'class': 'form-control'},
        )

    class Meta:
        """Конфигурация модели, исключённых полей и виджетов формы баллона."""

        model = Balloon
        exclude = ['user', 'change_date', 'miriada_status_error']
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
            'status': forms.Select(attrs={'class': 'form-control'}),
            'manufacturer': forms.TextInput(attrs={'class': 'form-control'}),
            'wall_thickness': forms.NumberInput(attrs={'class': 'form-control'}),
            'filling_status': forms.CheckboxInput(attrs={'class': 'form-control'}),
            'update_passport_required': forms.CheckboxInput(attrs={'class': 'form-control'})
        }


class BalloonsBatchForm(forms.ModelForm):
    """ModelForm партии баллонов (приёмка/отгрузка) для редактирования в веб-интерфейсе."""

    def __init__(self, *args, **kwargs):
        """
        Инициализирует форму партии, crispy-forms и подписи пустых значений.

        Скрывает поле ``batch_type`` и настраивает empty_label для транспорта.
        """
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
        self.fields['batch_type'].widget = forms.HiddenInput()
        self.fields['status'].widget.attrs.update({'class': 'form-control'})
        self.order_fields(['status'] + [name for name in self.fields if name != 'status'])

    class Meta:
        """Конфигурация исключённых полей, виджетов и подписей формы партии."""

        model = BalloonsBatch
        exclude = [
            'user',
            'balloon_list',
            'miriada_balloons_sent',
            'miriada_close_failed',
            'miriada_error_message',
            'miriada_status_errors',
        ]
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
            'amount_of_ttn': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Количество по электронной ТТН'
            })
        }
        labels = {
            'amount_of_ttn': 'Количество баллонов по электронной ТТН',
            'batch_type': 'Тип партии',
            'status': 'Статус партии',
        }
