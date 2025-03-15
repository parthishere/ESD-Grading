from django.contrib import admin
from labs.models import * 

class EvaluationRubricAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_default', 'get_total_max_marks')
    list_filter = ('is_default',)
    search_fields = ('name', 'description')

class GradeScaleAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_default', 'a_threshold', 'b_threshold', 'c_threshold', 'd_threshold')
    list_filter = ('is_default',)
    search_fields = ('name', 'description')
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'is_default')
        }),
        ('A Range', {
            'fields': ('a_plus_threshold', 'a_threshold', 'a_minus_threshold'),
            'classes': ('collapse',),
        }),
        ('B Range', {
            'fields': ('b_plus_threshold', 'b_threshold', 'b_minus_threshold'),
            'classes': ('collapse',),
        }),
        ('C Range', {
            'fields': ('c_plus_threshold', 'c_threshold', 'c_minus_threshold'),
            'classes': ('collapse',),
        }),
        ('D Range', {
            'fields': ('d_plus_threshold', 'd_threshold', 'd_minus_threshold'),
            'classes': ('collapse',),
        }),
    )

class LabAdmin(admin.ModelAdmin):
    list_display = ('name', 'due_date', 'total_points', 'grade_scale')
    list_filter = ('due_date',)
    search_fields = ('name', 'description')
    raw_id_fields = ('grade_scale',)

# Register your models here.
admin.site.register(Lab, LabAdmin)
admin.site.register(UserRole)
admin.site.register(Part)
admin.site.register(QualityCriteria)
admin.site.register(Student)
admin.site.register(Signoff)
admin.site.register(QualityScore)
admin.site.register(EvaluationSheet)
admin.site.register(EvaluationRubric, EvaluationRubricAdmin)
admin.site.register(GradeScale, GradeScaleAdmin)

