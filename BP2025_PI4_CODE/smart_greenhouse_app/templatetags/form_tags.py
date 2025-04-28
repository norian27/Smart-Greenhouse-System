from django import template
import json

register = template.Library()

@register.filter
def addclass(value, arg):
    if hasattr(value, 'as_widget'):
        return value.as_widget(attrs={'class': arg})
    return value

