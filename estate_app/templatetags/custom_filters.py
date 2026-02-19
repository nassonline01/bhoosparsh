from datetime import timedelta
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


@register.filter
def split(value, key):
    return value.split(key)

@register.filter
def status_filter(queryset, status):
    """Filter inquiries by status"""
    return queryset.filter(status=status)

@register.filter
def add_days(value, days):
    """
    Adds number of days to a date
    Usage: {{ some_date|add_days:7 }}
    """
    try:
        return value + timedelta(days=int(days))
    except Exception:
        return value

@register.filter
def count_by_status(queryset, status):
    """Count objects by status from a queryset"""
    if hasattr(queryset, 'filter'):
        # If it's still a queryset
        return queryset.filter(status=status).count()
    else:
        # If it's already a list (like paginated results)
        return sum(1 for obj in queryset if obj.status == status)

@register.filter
def filter_by_status(queryset, status):
    """Filter objects by status from a queryset or list"""
    if hasattr(queryset, 'filter'):
        # If it's still a queryset
        return queryset.filter(status=status)
    else:
        # If it's already a list (like paginated results)
        return [obj for obj in queryset if obj.status == status]

@register.filter
def get_source_display(source):
    """Get human-readable source name"""
    source_map = {
        'website': 'Website Form',
        'phone': 'Phone Call',
        'whatsapp': 'WhatsApp',
        'email': 'Email',
        'walkin': 'Walk-in',
    }
    return source_map.get(source, source.title())