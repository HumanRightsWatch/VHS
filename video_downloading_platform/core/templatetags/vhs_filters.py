from django import template

register = template.Library()

@register.filter
def hash_d(d, key):
    return d.get(key, 'NA')
