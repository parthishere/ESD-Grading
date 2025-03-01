from django.shortcuts import render
from django.http import JsonResponse
from .models import *
from django.shortcuts import render, redirect, reverse
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Avg, Sum, F, Q
from django.contrib.auth.decorators import login_required

# Create your views here.


# # Dashboard View
# @login_required
# def dashboard(request):
#     """Main dashboard view showing overall statistics."""
#     labs_count = Lab.objects.count()
#     parts_count = Part.objects.count()
#     students_count = Student.objects.count()
#     signoffs_count = Signoff.objects.count()
    
#     recent_signoffs = Signoff.objects.select_related('student', 'part', 'instructor').order_by('-date_updated')[:10]
    
#     # Calculate lab completion statistics
#     labs = Lab.objects.annotate(
#         total_parts=Count('parts', filter=F('parts__is_required') == True),
#         completed_signoffs=Count('parts__signoffs', 
#                                filter=F('parts__signoffs__status') == 'approved',
#                                distinct=True)
#     )
    
#     # Calculate total students with any approved signoffs
#     active_students = Student.objects.filter(signoffs__status='approved').distinct().count()
    
#     # Calculate overall completion percentage
#     total_required_parts = Part.objects.filter(is_required=True).count()
#     if total_required_parts > 0 and students_count > 0:
#         overall_completion = (Signoff.objects.filter(status='approved', part__is_required=True).count() / 
#                              (total_required_parts * students_count)) * 100
#     else:
#         overall_completion = 0
    
#     context = {
#         'labs_count': labs_count,
#         'parts_count': parts_count,
#         'students_count': students_count,
#         'active_students': active_students,
#         'signoffs_count': signoffs_count,
#         'recent_signoffs': recent_signoffs,
#         'labs': labs,
#         'overall_completion': overall_completion,
#     }
    
#     return render(request, 'labs/dashboard.html', context)


def home_view(request):
    
    labs_count = Lab.objects.count()
    parts_count = Part.objects.count()
    students_count = Student.objects.count()
    signoffs_count = Signoff.objects.count()
    
    recent_signoffs = Signoff.objects.select_related('student', 'part', 'instructor').order_by('-date_updated')[:10]
    
    # Calculate lab completion statistics
    labs = Lab.objects.annotate(
        total_parts=Count('parts', filter=F('parts__is_required') == True),
        completed_signoffs=Count('parts__signoffs', 
                               filter=F('parts__signoffs__status') == 'approved',
                               distinct=True)
    )
    
    # Calculate total students with any approved signoffs
    active_students = Student.objects.filter(signoffs__status='approved').distinct().count()
    
    # Calculate overall completion percentage
    total_required_parts = Part.objects.filter(is_required=True).count()
    if total_required_parts > 0 and students_count > 0:
        overall_completion = (Signoff.objects.filter(status='approved', part__is_required=True).count() / 
                             (total_required_parts * students_count)) * 100
    else:
        overall_completion = 0
    
    context = {
        'labs_count': labs_count,
        'parts_count': parts_count,
        'students_count': students_count,
        'active_students': active_students,
        'signoffs_count': signoffs_count,
        'recent_signoffs': recent_signoffs,
        'labs': labs,
        'overall_completion': overall_completion,
    }
    return render(request, 'labs/home.html', context=context)

@login_required
def student_name_search(request):
    """AJAX view to search for students by name with autocomplete functionality."""
    query = request.GET.get('query', '')
    if not query or len(query) < 2:  # Only search if query has at least 2 characters
        return JsonResponse({'students': []})
    
    # Search by name or student ID
    students = Student.objects.filter(
        Q(name__icontains=query) | 
        Q(student_id__icontains=query)
    ).values('id', 'name', 'student_id')[:10]  # Limit to 10 results
    
    return JsonResponse({'students': list(students)})


@login_required
def get_parts(request):
    """AJAX view to get parts for a lab."""
    lab_id = request.GET.get('lab_id', '')
    if not lab_id:
        return JsonResponse([])
    
    parts = Part.objects.filter(lab_id=lab_id).values('id', 'name')
    return JsonResponse(list(parts), safe=False)


@login_required
def get_criteria(request):
    """AJAX view to get quality criteria for a part."""
    part_id = request.GET.get('part_id', '')
    if not part_id:
        return JsonResponse([])
    
    criteria = QualityCriteria.objects.filter(part_id=part_id).values('id', 'name', 'max_points')
    return JsonResponse(list(criteria), safe=False)


@login_required
def quick_signoff(request):
    """Handle the AJAX submission of quick signoff form."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    student_id = request.POST.get('student_id')
    part_id = request.POST.get('part_id')
    comments = request.POST.get('comments', '')
    overall_score = request.POST.get('overall_score')
    
    try:
        student = Student.objects.get(student_id=student_id)
        part = Part.objects.get(id=part_id)
    except (Student.DoesNotExist, Part.DoesNotExist):
        return JsonResponse({'success': False, 'message': 'Student or Part not found'})
    
    # Determine status based on overall score
    status_map = {
        '0': 'rejected',  # Not Applicable - considered a rejection
        '1': 'rejected',  # Poor/Not Complete
        '2': 'approved',  # Meets Requirements
        '3': 'approved',  # Exceeds Requirements
        '4': 'approved'   # Outstanding
    }
    status = status_map.get(overall_score, 'pending')
    
    # Create or update signoff
    signoff, created = Signoff.objects.update_or_create(
        student=student,
        part=part,
        defaults={
            'instructor': request.user,
            'status': status,
            'comments': comments
        }
    )
    
    # Process individual criteria scores
    # for key, value in request.POST.items():
    #     if key.startswith('criteria_'):
    #         criteria_id = key.split('_')[1]
    #         try:
    #             criteria = QualityCriteria.objects.get(id=criteria_id)
                
    #             # Convert radio value to points based on criteria's max_points
    #             value_map = {
    #                 '0': 0,                               # Not Applicable
    #                 '1': criteria.max_points * 0.25,      # Poor/Not Complete - 25%
    #                 '2': criteria.max_points * 0.5,       # Meets Requirements - 50%
    #                 '3': criteria.max_points * 0.75,      # Exceeds Requirements - 75%
    #                 '4': criteria.max_points              # Outstanding - 100%
    #             }
    #             score = value_map.get(value, 0)
                
    #             # Create or update score
    #             QualityScore.objects.update_or_create(
    #                 signoff=signoff,
    #                 criteria=criteria,
    #                 defaults={'score': score}
    #             )
    #         except QualityCriteria.DoesNotExist:
    #             continue
    
    return JsonResponse({
        'success': True, 
        'message': f"Signoff {'created' if created else 'updated'} successfully",
        'signoff_id': signoff.id
    })
    
    
def lab_list(request):
    
    return render(request, "labs/lablist.html", context={})