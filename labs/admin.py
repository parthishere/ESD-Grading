from django.contrib import admin
from labs.models import * 

class EvaluationRubricAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_default', 'get_total_max_marks')
    list_filter = ('is_default',)
    search_fields = ('name', 'description')

# Register your models here.
admin.site.register(Lab)
admin.site.register(UserRole)
admin.site.register(Part)
admin.site.register(QualityCriteria)
admin.site.register(Student)
admin.site.register(Signoff)
admin.site.register(QualityScore)
admin.site.register(EvaluationSheet)
admin.site.register(EvaluationRubric, EvaluationRubricAdmin)

