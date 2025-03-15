# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('labs', '0002_create_evaluation_sheet'),
    ]

    operations = [
        migrations.CreateModel(
            name='EvaluationRubric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('is_default', models.BooleanField(default=False)),
                ('criteria_data', models.JSONField(default=dict)),
            ],
            options={
                'verbose_name': 'Evaluation Rubric',
                'verbose_name_plural': 'Evaluation Rubrics',
            },
        ),
        # The signoff field is already defined as CASCADE, so no need to alter
        # Add rubric field as nullable for now
        migrations.AddField(
            model_name='evaluationsheet',
            name='rubric',
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name='evaluation_sheets', to='labs.evaluationrubric'),
        ),
        migrations.AddField(
            model_name='evaluationsheet',
            name='evaluations',
            field=models.JSONField(default=dict),
        ),
    ]