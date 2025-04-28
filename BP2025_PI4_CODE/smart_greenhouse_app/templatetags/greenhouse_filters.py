from django import template
import json

register = template.Library()

@register.filter(name='split_and_get_first')
def split_and_get_first(value, delimiter=','):
    return value.split(delimiter)[0] if value else ''



@register.filter
def split_string(value, key):
    if value is None:
        return []
    return value.split(key)

@register.filter
def parse_json(value):
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}

@register.filter
def json_pretty(value):
    try:
        return json.dumps(json.loads(value), indent=2)
    except (TypeError, json.JSONDecodeError):
        return value