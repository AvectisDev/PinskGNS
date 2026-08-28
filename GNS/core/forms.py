from django import forms


class DateRangeForm(forms.Form):
    """Форма выбора периода дат для фильтрации списков."""

    start_date = forms.DateField(
        label='Начальная дата',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    end_date = forms.DateField(
        label='Конечная дата',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
