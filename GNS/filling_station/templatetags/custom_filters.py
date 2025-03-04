from django import template

register = template.Library()

@register.filter
def float_format(value):
    if value is None:
        return "-"
    return f"{float(value):.2f}"