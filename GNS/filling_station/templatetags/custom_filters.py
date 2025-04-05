from django import template

register = template.Library()

@register.filter
def float_format(value):
    if value is None:
        return "-"
    return f"{float(value):.2f}"

@register.filter
def default_dash(value):
    """
    Возвращает значение или '-', если значение пустое или None.
    """
    if value is None or value == '':
        return '-'
    return value