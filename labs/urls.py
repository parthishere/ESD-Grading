

from django.urls import path, include, re_path

from labs import views

app_name = 'labs'


urlpatterns = [
    path("", views.home_view, name="home"),
    
    path('labs/', views.lab_list, name='lab_list'),
    path('lab/<int:lab_id>/', views.lab_detail, name='lab_detail'),
    # path('lab/create/', views.lab_create, name='lab_create'),
    # path('lab/edit/<int:pk>/', views.lab_edit, name='lab_edit'),
    # path('lab/<int:lab_id>/parts/', views.part_list, name='part_list'),
    
    # Part management URLs
    path('part/<int:part_id>/', views.part_detail, name='part_detail'),
    # path('part/create/<int:lab_id>/', views.part_create, name='part_create'),
    # path('part/edit/<int:pk>/', views.part_edit, name='part_edit'),
    # path('part/<int:part_id>/criteria/', views.criteria_list, name='criteria_list'),
    
    # Criteria management URLs
    # path('criteria/create/<int:part_id>/', views.criteria_create, name='criteria_create'),
    # path('criteria/edit/<int:pk>/', views.criteria_edit, name='criteria_edit'),
    
    # Student management URLs
    path('students/', views.student_list, name='student_list'),
    path('students/upload/', views.student_upload, name='student_upload'),
    path('students/batch/', views.batch_toggle_students, name='batch_toggle_students'),
    path('student/toggle-active/<int:student_id>/', views.student_toggle_active, name='student_toggle_active'),
    path('student/<int:student_id>/', views.student_detail, name='student_detail'),
    # path('student/create/', views.student_create, name='student_create'),
    # path('student/edit/<int:pk>/', views.student_edit, name='student_edit'),
    
    # User management URLs
    path('users/', views.user_list, name='user_list'),
    path('user/create/', views.user_create, name='user_create'),
    path('user/edit/<int:user_id>/', views.user_edit, name='user_edit'),
    
    # Signoff management URLs
    path('signoffs/', views.signoff_list, name='signoff_list'),
    path('signoff/<int:signoff_id>/', views.signoff_detail, name='signoff_detail'),
    path('signoff/edit/<int:signoff_id>/', views.signoff_edit, name='signoff_edit'),
    # path('signoff/create/', views.signoff_create, name='signoff_create'),
    # path('quick-signoff/', views.quick_signoff, name='quick_signoff'),
    
    # AJAX endpoints
    path('api/student-name-search/', views.student_name_search, name='student_name_search'),
    path('api/get-signoffs/', views.get_existing_signoff, name='get_existing_signoff'),
    path('api/get-parts/', views.get_parts, name='get_parts'),
    path('api/get-criteria/', views.get_criteria, name='get_criteria'),
    path('api/quick-signoff/', views.quick_signoff_submit, name='quick_signoff_submit'),
    path('api/get-signoff-details/', views.get_signoff_details, name='get_signoff_details'),
    
    # Reports
    path('reports/', views.reports, name='reports'),
    path('reports/lab/', views.lab_report, name='lab_report_default'),
    path('reports/lab/<int:lab_id>/', views.lab_report, name='lab_report'),
    path('reports/students/', views.student_progress_report, name='student_progress_report'),
    path('reports/instructors/', views.ta_report, name='ta_report'),
    path('reports/grades/', views.student_grade_report, name='student_grade_report'),
    path('reports/grades/<int:student_id>/', views.student_grade_report, name='student_grade_report'),
    path('api/quick-stats/', views.quick_stats, name='quick_stats'),
    
    # CSV Exports
    path('export/lab/<int:lab_id>/csv/', views.export_lab_csv, name='export_lab_csv'),
    path('export/part/<int:part_id>/csv/', views.export_part_csv, name='export_part_csv'),
]
