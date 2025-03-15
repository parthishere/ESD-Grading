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
        
@register.filter(name='get_lab_completion')
def get_lab_completion(lab, student):
    """Get completion percentage for a student on a lab."""
    percentage = lab.get_student_percentage(student)
    return percentage

@register.filter(name='get_part_status')
def get_part_status(part, student):
    """Get status of a part for a student."""
    from labs.models import Signoff
    
    try:
        signoff = Signoff.objects.get(part=part, student=student)
        return signoff.status
    except Signoff.DoesNotExist:
        return "not_started"
        
@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Get an item from a dictionary using key.
    Usage: {{ dictionary|get_item:key }}
    """
    if not dictionary:
        return None
    return dictionary.get(key)