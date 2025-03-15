# Generated by Django 5.1.6 on 2025-03-15 08:05

import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('labs', '0005_remove_evaluationsheet_cleanliness_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='GradeScale',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('is_default', models.BooleanField(default=False)),
                ('a_plus_threshold', models.DecimalField(decimal_places=2, default=Decimal('97.0'), max_digits=5)),
                ('a_threshold', models.DecimalField(decimal_places=2, default=Decimal('93.0'), max_digits=5)),
                ('a_minus_threshold', models.DecimalField(decimal_places=2, default=Decimal('90.0'), max_digits=5)),
                ('b_plus_threshold', models.DecimalField(decimal_places=2, default=Decimal('87.0'), max_digits=5)),
                ('b_threshold', models.DecimalField(decimal_places=2, default=Decimal('83.0'), max_digits=5)),
                ('b_minus_threshold', models.DecimalField(decimal_places=2, default=Decimal('80.0'), max_digits=5)),
                ('c_plus_threshold', models.DecimalField(decimal_places=2, default=Decimal('77.0'), max_digits=5)),
                ('c_threshold', models.DecimalField(decimal_places=2, default=Decimal('73.0'), max_digits=5)),
                ('c_minus_threshold', models.DecimalField(decimal_places=2, default=Decimal('70.0'), max_digits=5)),
                ('d_plus_threshold', models.DecimalField(decimal_places=2, default=Decimal('67.0'), max_digits=5)),
                ('d_threshold', models.DecimalField(decimal_places=2, default=Decimal('63.0'), max_digits=5)),
                ('d_minus_threshold', models.DecimalField(decimal_places=2, default=Decimal('60.0'), max_digits=5)),
            ],
            options={
                'verbose_name': 'Grade Scale',
                'verbose_name_plural': 'Grade Scales',
            },
        ),
        migrations.AddField(
            model_name='lab',
            name='grade_scale',
            field=models.ForeignKey(blank=True, help_text='Grade scale to use for this lab', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='labs', to='labs.gradescale'),
        ),
    ]
