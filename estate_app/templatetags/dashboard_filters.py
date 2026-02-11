"""
Custom template filters for dashboard
"""
from django import template

register = template.Library()

@register.filter
def status_color(status):
    """Return Bootstrap color class for property status"""
    colors = {
        'for_sale': 'success',
        'for_rent': 'info',
        'sold': 'secondary',
        'rented': 'warning',
        'pending': 'primary',
        'draft': 'light',
    }
    return colors.get(status, 'secondary')

@register.filter
def inquiry_status_color(status):
    """Return Bootstrap color class for inquiry status"""
    colors = {
        'new': 'primary',
        'read': 'info',
        'contacted': 'success',
        'scheduled': 'warning',
        'negotiating': 'warning',
        'converted': 'success',
        'closed': 'secondary',
        'spam': 'danger',
    }
    return colors.get(status, 'secondary')

@register.filter
def user_type_color(user_type):
    """Return Bootstrap color class for user type"""
    colors = {
        'buyer': 'info',
        'seller': 'warning',
        'agent': 'success',
        'admin': 'danger',
    }
    return colors.get(user_type, 'secondary')

@register.filter
def activity_color(activity_type):
    """Return Bootstrap color class for activity type"""
    colors = {
        'property_approval': 'warning',
        'user_verification': 'info',
        'support_message': 'danger',
        'inquiry': 'primary',
        'view': 'info',
        'favorite': 'danger',
        'user': 'success',
        'property': 'warning',
    }
    return colors.get(activity_type, 'secondary')

@register.filter
def activity_icon(activity_type):
    """Return Font Awesome icon for activity type"""
    icons = {
        'property_approval': 'home',
        'user_verification': 'user-check',
        'support_message': 'envelope',
        'inquiry': 'envelope',
        'view': 'eye',
        'favorite': 'heart',
        'user': 'user-plus',
        'property': 'home',
    }
    return icons.get(activity_type, 'circle')

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    return dictionary.get(key, '')

@register.filter
def percentage(value):
    """Format value as percentage"""
    try:
        return f"{float(value):.1f}%"
    except (ValueError, TypeError):
        return "0.0%"

@register.filter
def format_currency(value):
    """Format value as currency"""
    try:
        return f"₹{float(value):,.0f}"
    except (ValueError, TypeError):
        return "₹0"
    
@register.filter
def split(value, delimiter=" "):
    """
    Usage: {{ "a b c"|split }}
    """
    return value.split(delimiter)    

@register.filter
def inquiry_status_color(status):
    """
    Returns bootstrap color class based on inquiry status
    """
    status_map = {
        'pending': 'warning',
        'new': 'info',
        'approved': 'success',
        'rejected': 'danger',
        'closed': 'secondary',
    }

    return status_map.get(str(status).lower(), 'dark')