from django import template

register = template.Library()

@register.filter
def has_role(user, role_name):
    """
    Check if a user has a specific role.
    Usage: {% if request.user|has_role:'instructor' %}
    """
    if user.is_anonymous:
        return False
    
    # Staff users can do everything
    if user.is_staff:
        return True
    
    # Check if user has the role object
    try:
        return hasattr(user, 'role') and user.role.role == role_name
    except:
        return False