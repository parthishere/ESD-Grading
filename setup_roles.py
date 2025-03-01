#!/usr/bin/env python
import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ESD.settings')
django.setup()

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from labs.models import Student, UserRole, Lab, Part, Signoff, QualityCriteria

def setup_role_permissions():
    """Setup Groups and Permissions for each role"""
    print("Setting up role permissions...")
    
    # Create groups if they don't exist
    instructor_group, _ = Group.objects.get_or_create(name='instructor')
    ta_group, _ = Group.objects.get_or_create(name='ta')
    student_group, _ = Group.objects.get_or_create(name='student')
    
    # Clear existing permissions
    instructor_group.permissions.clear()
    ta_group.permissions.clear()
    student_group.permissions.clear()
    
    # Get content types
    student_ct = ContentType.objects.get_for_model(Student)
    lab_ct = ContentType.objects.get_for_model(Lab)
    part_ct = ContentType.objects.get_for_model(Part)
    signoff_ct = ContentType.objects.get_for_model(Signoff)
    quality_ct = ContentType.objects.get_for_model(QualityCriteria)
    
    # Add permissions to instructor group (all permissions)
    for ct in [student_ct, lab_ct, part_ct, signoff_ct, quality_ct]:
        permissions = Permission.objects.filter(content_type=ct)
        for perm in permissions:
            instructor_group.permissions.add(perm)
    
    # TA permissions - can manage signoffs and quality scores, can view but not manage labs/parts
    ta_permissions = [
        Permission.objects.get(codename='add_signoff', content_type=signoff_ct),
        Permission.objects.get(codename='change_signoff', content_type=signoff_ct),
        Permission.objects.get(codename='view_signoff', content_type=signoff_ct),
        Permission.objects.get(codename='add_qualitycriteria', content_type=quality_ct),
        Permission.objects.get(codename='change_qualitycriteria', content_type=quality_ct),
        Permission.objects.get(codename='view_qualitycriteria', content_type=quality_ct),
        Permission.objects.get(codename='view_student', content_type=student_ct),
        Permission.objects.get(codename='view_lab', content_type=lab_ct),
        Permission.objects.get(codename='view_part', content_type=part_ct),
    ]
    for perm in ta_permissions:
        ta_group.permissions.add(perm)
    
    # Student permissions - can only view things
    student_permissions = [
        Permission.objects.get(codename='view_lab', content_type=lab_ct),
        Permission.objects.get(codename='view_part', content_type=part_ct),
        Permission.objects.get(codename='view_signoff', content_type=signoff_ct),
    ]
    for perm in student_permissions:
        student_group.permissions.add(perm)
    
    print("Role permissions set up successfully")

def create_superuser_if_needed():
    """Create a superuser if none exists"""
    if not User.objects.filter(is_superuser=True).exists():
        print("Creating superuser...")
        user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='Admin@123'
        )
        # Create instructor role for superuser
        UserRole.objects.create(user=user, role='instructor')
        print(f"Superuser '{user.username}' created with password 'Admin@123'")
    else:
        print("Superuser already exists, skipping creation")

if __name__ == "__main__":
    setup_role_permissions()
    create_superuser_if_needed()
    print("Setup complete!")