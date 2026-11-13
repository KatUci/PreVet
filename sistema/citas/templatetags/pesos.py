"""{{ valor|pesos }}: 25000 -> $25.000, como se escriben los montos en Chile."""

from django import template

register = template.Library()


@register.filter
def pesos(valor):
    try:
        return f'${int(valor):,}'.replace(',', '.')
    except (TypeError, ValueError):
        return ''
