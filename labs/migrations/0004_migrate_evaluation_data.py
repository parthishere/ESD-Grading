# Generated manually

from django.db import migrations

def create_default_rubric_and_migrate(apps, schema_editor):
    """Create a default evaluation rubric and migrate existing evaluation sheets."""
    # Get models
    EvaluationRubric = apps.get_model('labs', 'EvaluationRubric')
    EvaluationSheet = apps.get_model('labs', 'EvaluationSheet')
    
    # Create default rubric with standard criteria
    default_criteria = {
        "cleanliness": {"name": "Cleanliness", "max_marks": 5.0},
        "hardware": {"name": "Hardware", "max_marks": 10.0},
        "timeliness": {"name": "Timeliness", "max_marks": 5.0},
        "student_preparation": {"name": "Student Preparation", "max_marks": 10.0},
        "code_implementation": {"name": "Code Implementation", "max_marks": 15.0},
        "commenting": {"name": "Commenting", "max_marks": 5.0},
        "schematic": {"name": "Schematic", "max_marks": 10.0},
        "course_participation": {"name": "Course Participation", "max_marks": 5.0}
    }
    
    default_rubric = EvaluationRubric.objects.create(
        name="Default Rubric",
        description="Standard evaluation criteria for lab signoffs",
        is_default=True,
        criteria_data=default_criteria
    )
    
    # Migrate existing evaluation sheets to use the default rubric and store values in evaluations field
    for sheet in EvaluationSheet.objects.all():
        evaluations = {}
        
        try:
            evaluations["cleanliness"] = sheet.cleanliness
            evaluations["hardware"] = sheet.hardware
            evaluations["timeliness"] = sheet.timeliness
            evaluations["student_preparation"] = sheet.student_preparation
            evaluations["code_implementation"] = sheet.code_implementation
            evaluations["commenting"] = sheet.commenting
            evaluations["schematic"] = sheet.schematic
            evaluations["course_participation"] = sheet.course_participation
            
            sheet.evaluations = evaluations
            sheet.rubric = default_rubric
            sheet.save()
        except:
            # Older sheets might not have all fields, just skip them
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('labs', '0003_evaluation_rubric'),
    ]

    operations = [
        migrations.RunPython(create_default_rubric_and_migrate),
    ]