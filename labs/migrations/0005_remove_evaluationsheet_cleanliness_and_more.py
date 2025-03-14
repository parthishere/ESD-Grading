# Generated by Django 5.1.6 on 2025-03-15 07:26

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('labs', '0004_migrate_evaluation_data'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='evaluationsheet',
            name='cleanliness',
        ),
        migrations.RemoveField(
            model_name='evaluationsheet',
            name='cleanliness_max_marks',
        ),
        migrations.RemoveField(
            model_name='evaluationsheet',
            name='code_implementation',
        ),
        migrations.RemoveField(
            model_name='evaluationsheet',
            name='code_implementation_max_marks',
        ),
        migrations.RemoveField(
            model_name='evaluationsheet',
            name='commenting',
        ),
        migrations.RemoveField(
            model_name='evaluationsheet',
            name='commenting_max_marks',
        ),
        migrations.RemoveField(
            model_name='evaluationsheet',
            name='course_participation',
        ),
        migrations.RemoveField(
            model_name='evaluationsheet',
            name='course_participation_max_marks',
        ),
        migrations.RemoveField(
            model_name='evaluationsheet',
            name='hardware',
        ),
        migrations.RemoveField(
            model_name='evaluationsheet',
            name='hardware_max_marks',
        ),
        migrations.RemoveField(
            model_name='evaluationsheet',
            name='schematic',
        ),
        migrations.RemoveField(
            model_name='evaluationsheet',
            name='schematic_max_marks',
        ),
        migrations.RemoveField(
            model_name='evaluationsheet',
            name='student_preparation',
        ),
        migrations.RemoveField(
            model_name='evaluationsheet',
            name='student_preparation_max_marks',
        ),
        migrations.RemoveField(
            model_name='evaluationsheet',
            name='timeliness',
        ),
        migrations.RemoveField(
            model_name='evaluationsheet',
            name='timeliness_max_marks',
        ),
    ]
