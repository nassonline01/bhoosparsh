from django import template

register = template.Library()

@register.filter
def replace(value, arg):
    """
    Usage: {{ value|replace:"old|new" }}
    """
    if '|' not in arg:
        return value  # Return original value if no separator found
    parts = arg.split('|', 1)  # Split only on first occurrence
    if len(parts) == 2:
        old, new = parts
        return value.replace(old, new)
    return value  # Return original value if split doesn't work as expected
