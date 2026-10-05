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


@register.filter
def get_item(mapping, key):
    """
    Возвращает значение по ключу из словаря (для шаблонов).

    Args:
        mapping: словарь или None.
        key: ключ для поиска.

    Returns:
        значение или None, если ключа нет.
    """
    if not mapping:
        return None
    return mapping.get(key)


@register.simple_tag
def get_post_correction(settings, post_num):
    """
    Для отображения корректоров карусели
    """
    return getattr(settings, f'post_{post_num}_correction', 0.0)

