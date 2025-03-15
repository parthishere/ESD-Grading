from django.contrib import admin
from labs.models import * 

# Register your models here.
admin.site.register(Lab)
admin.site.register(UserRole)
admin.site.register(Part)
admin.site.register(QualityCriteria)
admin.site.register(Student)
admin.site.register(Signoff)
admin.site.register(QualityScore)
admin.site.register(EvaluationSheet)

