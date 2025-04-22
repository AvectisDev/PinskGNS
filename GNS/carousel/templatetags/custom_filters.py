from django import template

register = template.Library()

@register.filter
def float_format(value):
    if value in (None, '', ' ', 'None'):
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

@register.simple_tag
def get_post_correction(settings, post_num):
    """
    Для отображения корректоров карусели
    """
    return getattr(settings, f'post_{post_num}_correction', 0.0)

