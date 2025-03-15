from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseRedirect, HttpResponse
from .models import *
from .forms import StudentUploadForm, UserRoleForm
from django.shortcuts import render, redirect, reverse
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test, login_required
from django.db.models import Count, Avg, Sum, F, Q, Case, When, Value, IntegerField
import datetime
from django.utils import timezone
from decimal import Decimal
import pandas as pd
import csv
import json
from io import BytesIO, StringIO
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.db.models.functions import Coalesce

# Define role check decorators
def instructor_required(function):
    """Decorator to check if user is an instructor."""
    def wrap(request, *args, **kwargs):
        try:
            if hasattr(request.user, 'role') and request.user.role.role in ['instructor']:
                return function(request, *args, **kwargs)
            else:
                raise PermissionDenied("You must be an instructor to access this page.")
        except (AttributeError, UserRole.DoesNotExist):
            raise PermissionDenied("You must be an instructor to access this page.")
    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap

def ta_required(function):
    """Decorator to check if user is a teaching assistant or instructor."""
    def wrap(request, *args, **kwargs):
        try:
            if hasattr(request.user, 'role') and request.user.role.role in ['ta', 'instructor']:
                return function(request, *args, **kwargs)
            else:
                raise PermissionDenied("You must be a teaching assistant or instructor to access this page.")
        except (AttributeError, UserRole.DoesNotExist):
            raise PermissionDenied("You must be a teaching assistant or instructor to access this page.")
    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap

# Home view
@login_required
def home_view(request):
    """Home view that shows quick signoff UI."""
    # Get all labs
    labs = Lab.objects.all().order_by('name')
    
    # Log the found labs for debugging
    print(f"Found {labs.count()} labs in home_view")
    for lab in labs:
        print(f"Lab: {lab.id} - {lab.name}")
        parts_count = lab.parts.count()
        print(f"  - Parts count: {parts_count}")
        if parts_count > 0:
            for part in lab.parts.all():
                print(f"    - Part: {part.id} - {part.name}")
    
    # Get pre-selected lab and part from query parameters (if any)
    selected_lab_id = request.GET.get('lab_id')
    selected_part_id = request.GET.get('part_id')
    selected_student_id = request.GET.get('student_id')
    
    # Set up initial context
    context = {
        'labs': labs,
        'selected_lab_id': selected_lab_id,
        'selected_part_id': selected_part_id,
        'selected_student_id': selected_student_id
    }
    
    return render(request, 'labs/home.html', context)

@login_required
def lab_list(request):
    """List all labs."""
    labs = Lab.objects.all()
    return render(request, 'labs/lablist.html', {'labs': labs})

@login_required
def lab_detail(request, lab_id):
    """View details for a lab."""
    lab = get_object_or_404(Lab, pk=lab_id)
    return render(request, 'labs/lab_detail.html', {'lab': lab})

@login_required
def part_detail(request, part_id):
    """View details for a lab part."""
    part = get_object_or_404(Part, pk=part_id)
    return render(request, 'labs/part_detail.html', {'part': part})

@login_required
def student_list(request):
    """List all students with search and filter functionality."""
    # Get search and filter parameters
    search_query = request.GET.get('search', '').strip()
    active_filter = request.GET.get('active', 'all')
    
    # Start with all students
    students = Student.objects.all()
    
    # Apply search filter if provided
    if search_query:
        students = students.filter(
            Q(name__icontains=search_query) | 
            Q(student_id__icontains=search_query) | 
            Q(email__icontains=search_query)
        )
    
    # Apply active status filter
    if active_filter == 'active':
        students = students.filter(active=True)
    elif active_filter == 'inactive':
        students = students.filter(active=False)
    
    # Count stats
    total_students = Student.objects.count()
    active_students = Student.objects.filter(active=True).count()
    inactive_students = Student.objects.filter(active=False).count()
    
    # Order students by name
    students = students.order_by('name')
    
    context = {
        'students': students,
        'search_query': search_query,
        'active_filter': active_filter,
        'total_students': total_students,
        'active_students': active_students,
        'inactive_students': inactive_students
    }
    
    return render(request, 'labs/student_list.html', context)

@login_required
def student_upload(request):
    """Upload student data from Excel."""
    return render(request, 'labs/student_upload.html')

@login_required
def batch_toggle_students(request):
    """Toggle active status for multiple students."""
    if request.method == 'POST':
        action = request.POST.get('action')
        batch_date = request.POST.get('batch_date')
        student_ids = request.POST.getlist('student_ids')
        
        # Validate the action
        if action not in ['activate', 'deactivate']:
            messages.error(request, 'Invalid action specified.')
            return redirect('labs:batch_toggle_students')
        
        # Process by batch date (year and month)
        if batch_date:
            try:
                batch_date = datetime.datetime.strptime(batch_date, '%Y-%m-%d').date()
                # Get students created in same year and month
                students = Student.objects.filter(
                    batch__year=batch_date.year,
                    batch__month=batch_date.month
                )
                
                # Apply the action
                count = 0
                for student in students:
                    student.active = (action == 'activate')
                    student.save()
                    count += 1
                
                messages.success(request, f'{count} students {action}d successfully from batch {batch_date.strftime("%B %Y")}')
                
            except (ValueError, TypeError):
                messages.error(request, 'Invalid batch date format.')
        
        # Process by individual student IDs
        elif student_ids:
            count = 0
            for student_id in student_ids:
                try:
                    student = Student.objects.get(pk=student_id)
                    student.active = (action == 'activate')
                    student.save()
                    count += 1
                except Student.DoesNotExist:
                    continue
            
            messages.success(request, f'{count} students {action}d successfully')
        
        else:
            messages.warning(request, 'No students selected for processing')
        
        return redirect('labs:student_list')
    
    # For GET requests, show the form
    students = Student.objects.all().order_by('-batch', 'name')
    
    # Get unique batch dates
    batches = Student.objects.dates('batch', 'day', order='DESC')
    
    context = {
        'students': students,
        'batches': batches
    }
    
    return render(request, 'labs/batch_toggle_students.html', context)

@login_required
def student_toggle_active(request, student_id):
    """Toggle active status for a student."""
    student = get_object_or_404(Student, pk=student_id)
    student.active = not student.active
    student.save()
    return redirect('labs:student_list')

@login_required
def student_detail(request, student_id):
    """View details for a student."""
    student = get_object_or_404(Student, pk=student_id)
    return render(request, 'labs/student_detail.html', {'student': student})

@login_required
def user_list(request):
    """List all users."""
    users = User.objects.all()
    return render(request, 'labs/user_list.html', {'users': users})

@login_required
def user_create(request):
    """Create a new user."""
    return render(request, 'labs/user_form.html')

@login_required
def user_edit(request, user_id):
    """Edit a user."""
    user = get_object_or_404(User, pk=user_id)
    return render(request, 'labs/user_form.html', {'user': user})

@login_required
def signoff_list(request):
    """List all signoffs with optional filters."""
    # Get filter parameters
    status_filter = request.GET.get('status')
    lab_filter = request.GET.get('lab_id')
    student_filter = request.GET.get('student_id')
    
    # Start with all signoffs
    signoffs = Signoff.objects.all()
    
    # Apply filters if provided
    if status_filter:
        signoffs = signoffs.filter(status=status_filter)
    
    if lab_filter:
        signoffs = signoffs.filter(part__lab_id=lab_filter)
    
    if student_filter:
        signoffs = signoffs.filter(student_id=student_filter)
    
    # Order by most recent first
    signoffs = signoffs.order_by('-date_updated')
    
    # Get all labs and students for filter dropdowns
    labs = Lab.objects.all().order_by('name')
    students = Student.objects.filter(active=True).order_by('name')
    
    context = {
        'signoffs': signoffs,
        'labs': labs,
        'students': students,
        'status_filter': status_filter,
        'lab_filter': lab_filter,
        'student_filter': student_filter
    }
    
    return render(request, 'labs/signoff_list.html', context)

@login_required
def signoff_detail(request, signoff_id):
    """View details for a signoff."""
    signoff = get_object_or_404(Signoff, pk=signoff_id)
    return render(request, 'labs/signoff_detail.html', {'signoff': signoff})

@login_required
def signoff_edit(request, signoff_id):
    """Edit a signoff."""
    signoff = get_object_or_404(Signoff, pk=signoff_id)
    return render(request, 'labs/signoff_edit.html', {'signoff': signoff})

@login_required
def student_name_search(request):
    """Search for students by name or ID."""
    query = request.GET.get('query', '').strip()
    results = []
    
    if query:
        # Search for students whose name or ID contains the query
        students = Student.objects.filter(
            Q(name__icontains=query) | Q(student_id__icontains=query),
            active=True
        )[:10]  # Limit to 10 results
        
        # Format results for autocomplete
        for student in students:
            results.append({
                'id': student.id,
                'student_id': student.student_id,
                'name': student.name,
                'email': student.email,
                'display': f"{student.name} ({student.student_id})"
            })
    
    # Return both results and students for compatibility with different JS approaches
    return JsonResponse({
        'results': results,
        'students': results
    })

@login_required
def get_existing_signoff(request):
    """Get existing signoff data for a student and lab."""
    student_id = request.GET.get('student_id')
    lab_id = request.GET.get('lab_id')
    
    if not student_id or not lab_id:
        return JsonResponse([])
    
    try:
        # Get student and lab - try by primary key first, then by student_id field
        try:
            # Try to get by primary key first
            student = Student.objects.get(pk=student_id)
        except (Student.DoesNotExist, ValueError):
            # If that fails, try to get by student_id field
            student = Student.objects.get(student_id=student_id)
            
        lab = Lab.objects.get(pk=lab_id)
        
        # Get all parts for this lab
        parts = Part.objects.filter(lab=lab)
        
        # Get all signoffs for this student and these parts
        signoffs = Signoff.objects.filter(
            student=student,
            part__in=parts
        ).select_related('part')
        
        signoff_data = []
        for signoff in signoffs:
            signoff_data.append({
                'id': signoff.id,
                'part_id': signoff.part.id,
                'status': signoff.status,
                'date_updated': signoff.date_updated.isoformat()
            })
        
        return JsonResponse(signoff_data, safe=False)
    except (Student.DoesNotExist, Lab.DoesNotExist):
        return JsonResponse([], safe=False)

@login_required
def get_parts(request):
    """Get parts for a lab."""
    lab_id = request.GET.get('lab_id')
    
    if not lab_id:
        return JsonResponse({'parts': []})
    
    try:
        lab = Lab.objects.get(pk=lab_id)
        parts = lab.parts.all().order_by('order')
        
        parts_data = []
        for part in parts:
            parts_data.append({
                'id': part.id,
                'name': part.name,
                'description': part.description,
                'required': part.is_required,
                'order': part.order
            })
        
        # Return the parts directly for compatibility with existing JS
        return JsonResponse(parts_data, safe=False)
    except Lab.DoesNotExist:
        return JsonResponse([], safe=False)

@login_required
def get_criteria(request):
    """Get criteria for a part."""
    part_id = request.GET.get('part_id')
    
    if not part_id:
        return JsonResponse({'criteria': []})
    
    try:
        part = Part.objects.get(pk=part_id)
        criteria = part.quality_criteria.all()
        
        # If no criteria exist, create default criteria
        if not criteria.exists():
            print(f"No criteria found for part {part_id}, creating defaults...")
            part.create_default_criteria()
            # Refresh the criteria after creating defaults
            criteria = part.quality_criteria.all()
        
        criteria_data = []
        for criterion in criteria:
            criteria_data.append({
                'id': criterion.id,
                'name': criterion.name,
                'description': criterion.description,
                'max_points': criterion.max_points,
                'weight': criterion.weight
            })
        
        # Get evaluation rubric criteria if a rubric is used
        # This will provide the fixed evaluation criteria
        evaluation_rubric = EvaluationRubric.get_default_rubric()
        rubric_criteria = []
        
        for key, criterion in evaluation_rubric.criteria_data.items():
            rubric_criteria.append({
                'key': key,
                'name': criterion['name'],
                'max_marks': criterion['max_marks']
            })
        
        # Get challenges for this part if it has challenges
        challenges_data = []
        if part.has_challenges:
            challenges = part.challenges.all().order_by('order')
            for challenge in challenges:
                challenges_data.append({
                    'id': challenge.id,
                    'name': challenge.name,
                    'description': challenge.description,
                    'max_points': challenge.max_points,
                    'difficulty': challenge.difficulty,
                    'order': challenge.order
                })
        
        response_data = {
            'criteria': criteria_data,
            'rubric_criteria': rubric_criteria,
            'has_challenges': part.has_challenges,
            'challenges': challenges_data
        }
        
        # Log the response data for debugging
        print(f"Response data for part {part_id}: {response_data}")
        
        return JsonResponse(response_data)
    except Part.DoesNotExist:
        return JsonResponse({'criteria': [], 'error': 'Part not found'}, status=404)
    except Exception as e:
        print(f"Error in get_criteria: {str(e)}")
        return JsonResponse({'criteria': [], 'error': str(e)}, status=500)

@login_required
def quick_signoff_submit(request):
    """Submit a quick signoff."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)
    
    # Get form data
    try:
        # Log the raw request body for debugging
        print(f"Raw request body: {request.body}")
        
        data = json.loads(request.body)
        student_id = data.get('student_id')
        part_id = data.get('part_id')
        comments = data.get('comments', '')
        overall_score = data.get('overall_score', 2)
        criteria_scores = data.get('criteria_scores', {})
        rubric_evaluations = data.get('rubric_evaluations', {})
        challenge_scores = data.get('challenge_scores', {})
        
        # Log the parsed data for debugging
        print(f"Parsed data: student_id={student_id}, part_id={part_id}")
        print(f"criteria_scores: {criteria_scores}")
        print(f"rubric_evaluations: {rubric_evaluations}")
        print(f"challenge_scores: {challenge_scores}")
        
        # Validate required fields
        if not student_id or not part_id:
            return JsonResponse({'success': False, 'error': 'Missing required fields'}, status=400)
        
        # Get student and part
        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            print(f"Student with ID {student_id} not found")
            return JsonResponse({'success': False, 'error': f'Student with ID {student_id} not found'}, status=404)
            
        try:
            part = Part.objects.get(pk=part_id)
        except Part.DoesNotExist:
            print(f"Part with ID {part_id} not found")
            return JsonResponse({'success': False, 'error': f'Part with ID {part_id} not found'}, status=404)
        
        # Check if part has quality criteria, create if not
        if not part.quality_criteria.exists():
            print(f"Part {part_id} has no quality criteria, creating defaults...")
            part.create_default_criteria()
        
        # Check if a signoff already exists for this student and part
        signoff, created = Signoff.objects.get_or_create(
            student=student,
            part=part,
            defaults={
                'instructor': request.user,
                'status': 'approved',
                'comments': comments
            }
        )
        
        if not created:
            # Update existing signoff
            signoff.instructor = request.user
            signoff.status = 'approved'
            signoff.comments = comments
            signoff.save()
        
        # Save quality criteria scores
        for criteria_id, score in criteria_scores.items():
            try:
                criteria = QualityCriteria.objects.get(pk=criteria_id)
                # Convert score to integer if it's a string
                if isinstance(score, str):
                    score = int(score)
                quality_score, _ = QualityScore.objects.update_or_create(
                    signoff=signoff,
                    criteria=criteria,
                    defaults={'score': score}
                )
            except QualityCriteria.DoesNotExist:
                print(f"Quality criteria with ID {criteria_id} not found")
                # Skip invalid criteria IDs
                continue
            except Exception as e:
                print(f"Error saving quality score for criteria {criteria_id}: {str(e)}")
                # Skip errors and continue
                continue
        
        # Create or update evaluation sheet with the fixed rubric
        rubric = EvaluationRubric.get_default_rubric()
        
        # If no rubric evaluations provided, create default ones
        if not rubric_evaluations:
            rubric_evaluations = {key: 'MR' for key in rubric.criteria_data.keys()}
        
        eval_sheet, _ = EvaluationSheet.objects.get_or_create(
            signoff=signoff,
            defaults={
                'rubric': rubric,
                'evaluations': rubric_evaluations
            }
        )
        
        if not _:
            # Update existing evaluation sheet
            eval_sheet.rubric = rubric
            eval_sheet.evaluations = rubric_evaluations
            eval_sheet.save()
            
        # If part has challenges, save challenge scores
        if part.has_challenges and challenge_scores:
            for challenge_id, score in challenge_scores.items():
                try:
                    challenge = Challenge.objects.get(pk=challenge_id)
                    # Convert score to integer if it's a string
                    if isinstance(score, str):
                        score = int(score)
                    # Make sure score doesn't exceed max points
                    score = min(score, challenge.max_points)
                    
                    challenge_score, _ = ChallengeScore.objects.update_or_create(
                        signoff=signoff,
                        challenge=challenge,
                        defaults={'score': score}
                    )
                except Challenge.DoesNotExist:
                    print(f"Challenge with ID {challenge_id} not found")
                    # Skip invalid challenge IDs
                    continue
                except Exception as e:
                    print(f"Error saving challenge score for challenge {challenge_id}: {str(e)}")
                    # Skip errors and continue
                    continue
        
        return JsonResponse({
            'success': True,
            'signoff_id': signoff.id,
            'status': 'approved',
            'message': 'Signoff successfully submitted'
        })
        
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        print(f"Error in signoff submission: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def get_signoff_details(request):
    """Get details for a signoff."""
    student_id = request.GET.get('student_id')
    part_id = request.GET.get('part_id')
    
    if not student_id or not part_id:
        return JsonResponse({'found': False})
    
    try:
        # Get student and part - try by primary key first, then by student_id field
        try:
            # Try to get by primary key first
            student = Student.objects.get(pk=student_id)
        except (Student.DoesNotExist, ValueError):
            # If that fails, try to get by student_id field
            student = Student.objects.get(student_id=student_id)
            
        part = Part.objects.get(pk=part_id)
        
        # Check if signoff exists
        try:
            signoff = Signoff.objects.get(student=student, part=part)
            
            # Get quality scores
            quality_scores = []
            for score in signoff.quality_scores.all():
                quality_scores.append({
                    'criteria_id': score.criteria.id,
                    'score': score.score,
                    'criteria__max_points': score.criteria.max_points
                })
            
            # Get evaluation sheet if it exists
            evaluation_sheet_data = {}
            has_evaluation_sheet = False
            
            try:
                eval_sheet = signoff.evaluation_sheet.first()
                if eval_sheet:
                    has_evaluation_sheet = True
                    
                    # If it's using the new rubric-based system
                    if hasattr(eval_sheet, 'rubric') and eval_sheet.rubric:
                        for key, value in eval_sheet.evaluations.items():
                            if key in eval_sheet.rubric.criteria_data:
                                evaluation_sheet_data[key] = {
                                    'value': value,
                                    'max_marks': eval_sheet.rubric.criteria_data[key]['max_marks']
                                }
                    else:
                        # Legacy system
                        evaluation_sheet_data = {
                            'cleanliness': {
                                'value': eval_sheet.cleanliness,
                                'max_marks': eval_sheet.cleanliness_max_marks
                            },
                            'hardware': {
                                'value': eval_sheet.hardware,
                                'max_marks': eval_sheet.hardware_max_marks
                            },
                            'timeliness': {
                                'value': eval_sheet.timeliness,
                                'max_marks': eval_sheet.timeliness_max_marks
                            },
                            'student_preparation': {
                                'value': eval_sheet.student_preparation,
                                'max_marks': eval_sheet.student_preparation_max_marks
                            },
                            'code_implementation': {
                                'value': eval_sheet.code_implementation,
                                'max_marks': eval_sheet.code_implementation_max_marks
                            },
                            'commenting': {
                                'value': eval_sheet.commenting,
                                'max_marks': eval_sheet.commenting_max_marks
                            },
                            'schematic': {
                                'value': eval_sheet.schematic,
                                'max_marks': eval_sheet.schematic_max_marks
                            },
                            'course_participation': {
                                'value': eval_sheet.course_participation,
                                'max_marks': eval_sheet.course_participation_max_marks
                            }
                        }
            except:
                pass
                
            # Get challenge scores if part has challenges
            challenge_scores = []
            has_challenges = part.has_challenges
            
            if has_challenges:
                challenges = part.challenges.all().order_by('order')
                for challenge in challenges:
                    try:
                        score = ChallengeScore.objects.get(signoff=signoff, challenge=challenge)
                        challenge_scores.append({
                            'challenge_id': challenge.id,
                            'name': challenge.name,
                            'score': score.score,
                            'max_points': challenge.max_points,
                            'difficulty': challenge.difficulty,
                            'comments': score.comments
                        })
                    except ChallengeScore.DoesNotExist:
                        challenge_scores.append({
                            'challenge_id': challenge.id,
                            'name': challenge.name,
                            'score': 0,
                            'max_points': challenge.max_points,
                            'difficulty': challenge.difficulty,
                            'comments': ''
                        })
            
            # Get signoff history
            history = []
            # In a real implementation, you would fetch history records here
            
            return JsonResponse({
                'found': True,
                'id': signoff.id,
                'status': signoff.status,
                'comments': signoff.comments,
                'date_updated': signoff.date_updated.isoformat(),
                'quality_scores': quality_scores,
                'has_evaluation_sheet': has_evaluation_sheet,
                'evaluation_sheet': evaluation_sheet_data,
                'has_challenges': has_challenges,
                'challenge_scores': challenge_scores,
                'history': history
            })
        except Signoff.DoesNotExist:
            return JsonResponse({'found': False})
            
    except (Student.DoesNotExist, Part.DoesNotExist):
        return JsonResponse({'found': False, 'error': 'Student or part not found'}, status=404)

@login_required
def reports(request):
    """View reports dashboard."""
    report_types = [
        {
            'id': 'lab_report',
            'name': 'Lab Report',
            'description': 'Generate a report for specific lab, showing student completion status and grades.'
        },
        {
            'id': 'student_report',
            'name': 'Student Progress Report',
            'description': 'Track progress of all students across different labs and parts.'
        },
        {
            'id': 'ta_report',
            'name': 'Instructor Activity Report',
            'description': 'View activity statistics for teaching assistants and instructors.'
        },
        {
            'id': 'grade_report',
            'name': 'Student Grade Report',
            'description': 'Generate comprehensive grade report for all students or individual student.'
        }
    ]
    
    labs = Lab.objects.all().order_by('name')
    students = Student.objects.filter(active=True)
    
    context = {
        'report_types': report_types,
        'labs': labs,
        'students': students
    }
    
    return render(request, 'labs/reports/dashboard.html', context)

@login_required
def lab_report(request, lab_id=None):
    """View report for a lab showing student progress for each part."""
    # Check for CSV export format
    if request.GET.get('format') == 'csv':
        return export_lab_csv(request, lab_id)
    
    # Get all labs for dropdown
    all_labs = Lab.objects.all().order_by('name')
    
    if not lab_id and all_labs.exists():
        # If no lab_id specified but labs exist, redirect to the first lab
        return redirect('labs:lab_report', lab_id=all_labs.first().id)
    
    if lab_id:
        lab = get_object_or_404(Lab, pk=lab_id)
        # Get all parts for this lab
        parts = lab.parts.all().order_by('order')
        # Get all students
        students = Student.objects.filter(active=True).order_by('name')
        
        # Create a list of other labs (excluding current)
        other_labs = all_labs.exclude(pk=lab_id)
        
        # Build data matrix for the report
        matrix = []
        
        for student in students:
            row = {
                'student': student,
                'parts': [],
                'completion': 0
            }
            
            completed_parts = 0
            total_parts = parts.count()
            
            for part in parts:
                status = part.get_part_status(student)
                
                # Calculate CSS class based on status
                if status == 'approved':
                    css_class = 'bg-success text-white'
                    completed_parts += 1
                elif status == 'pending':
                    css_class = 'bg-warning'
                elif status == 'rejected':
                    css_class = 'bg-danger text-white'
                else:  # not_started
                    css_class = 'bg-light'
                
                row['parts'].append({
                    'part': part,
                    'status': status,
                    'css_class': css_class
                })
            
            # Calculate completion percentage for this student
            if total_parts > 0:
                row['completion'] = (completed_parts / total_parts) * 100
            
            matrix.append(row)
        
        # Calculate overall stats
        completed_signoffs = Signoff.objects.filter(
            student__in=students,
            part__in=parts,
            status='approved'
        ).count()
        
        total_signoffs = students.count() * parts.count()
        
        # Count signoffs by status
        signoffs_by_status = {
            'approved': completed_signoffs,
            'pending': Signoff.objects.filter(
                student__in=students,
                part__in=parts,
                status='pending'
            ).count(),
            'rejected': Signoff.objects.filter(
                student__in=students,
                part__in=parts,
                status='rejected'
            ).count()
        }
        
        not_started = total_signoffs - (
            signoffs_by_status['approved'] + 
            signoffs_by_status['pending'] + 
            signoffs_by_status['rejected']
        )
        
        if total_signoffs > 0:
            completion_percent = (completed_signoffs / total_signoffs) * 100
        else:
            completion_percent = 0
        
        stats = {
            'completed': signoffs_by_status['approved'],
            'pending': signoffs_by_status['pending'],
            'rejected': signoffs_by_status['rejected'],
            'not_started': not_started,
            'total': total_signoffs,
            'completion_percent': completion_percent,
            'started': signoffs_by_status['pending'] + signoffs_by_status['rejected']
        }
        
        return render(request, 'labs/reports/lab_report.html', {
            'lab': lab,
            'parts': parts,
            'students': students,
            'all_labs': all_labs,
            'other_labs': other_labs,
            'matrix': matrix,
            'stats': stats
        })
    
    # If no lab_id specified and no labs exist
    return render(request, 'labs/reports/lab_report.html', {
        'all_labs': all_labs,
        'no_labs': True
    })

@login_required
def student_progress_report(request):
    """View progress report for all students across all labs."""
    # Get all active students
    students = Student.objects.filter(active=True).order_by('name')
    
    # Get all labs
    labs = Lab.objects.all().order_by('name')
    
    # Build data matrix for the report
    matrix = []
    
    for student in students:
        row = {
            'student': student,
            'labs': [],
            'overall_completion': student.get_completion_status
        }
        
        for lab in labs:
            # Calculate completion percentage for this lab
            completion = lab.get_student_percentage(student)
            
            # Determine CSS class based on completion
            if completion >= 90:
                css_class = 'bg-success text-white'
            elif completion >= 70:
                css_class = 'bg-info text-white'
            elif completion >= 50:
                css_class = 'bg-warning'
            elif completion > 0:
                css_class = 'bg-danger text-white'
            else:
                css_class = 'bg-light'
            
            row['labs'].append({
                'lab': lab,
                'completion': completion,
                'css_class': css_class,
                'grade': lab.get_grade_letter(student)
            })
        
        matrix.append(row)
    
    # Calculate overall statistics
    total_students = students.count()
    total_labs = labs.count()
    
    # Count students with 100% completion
    fully_completed = 0
    total_completion = 0
    
    for student in students:
        completion = student.get_completion_status
        total_completion += completion
        if completion == 100:
            fully_completed += 1
    
    if total_students > 0:
        overall_completion = total_completion / total_students
    else:
        overall_completion = 0
    
    stats = {
        'total_students': total_students,
        'total_labs': total_labs,
        'fully_completed': fully_completed,
        'overall_completion': overall_completion
    }
    
    return render(request, 'labs/reports/student_progress.html', {
        'students': students,
        'labs': labs,
        'matrix': matrix,
        'stats': stats
    })

@login_required
def ta_report(request):
    """View TA report."""
    # Get all instructors (users who can sign off)
    instructors = User.objects.filter(
        Q(groups__name='Instructor') | Q(groups__name='Admin') | Q(is_superuser=True)
    ).distinct()
    
    # Get all signoffs
    all_signoffs = Signoff.objects.all()
    approved_signoffs = all_signoffs.filter(status='approved')
    
    # Get signoffs for today
    today = timezone.now().date()
    signoffs_today = all_signoffs.filter(date_updated__date=today).count()
    
    # Get total signoffs
    total_signoffs = all_signoffs.count()
    
    # Build instructor stats
    instructor_stats = []
    
    for instructor in instructors:
        # Get all signoffs by this instructor
        instructor_signoffs = all_signoffs.filter(instructor=instructor)
        total_signoffs_count = instructor_signoffs.count()
        
        # Get counts by status
        approved_count = instructor_signoffs.filter(status='approved').count()
        rejected_count = instructor_signoffs.filter(status='rejected').count()
        pending_count = instructor_signoffs.filter(status='pending').count()
        
        # Get signoffs by this instructor today
        instructor_signoffs_today = instructor_signoffs.filter(date_updated__date=today).count()
        
        # Calculate average score given by instructor
        avg_score = 0
        total_points = 0
        max_points = 0
        
        # Calculate average from quality scores
        quality_scores = QualityScore.objects.filter(signoff__instructor=instructor)
        for score in quality_scores:
            total_points += score.score
            max_points += score.criteria.max_points
        
        # Add evaluation sheet scores
        eval_sheets = EvaluationSheet.objects.filter(signoff__instructor=instructor)
        for sheet in eval_sheets:
            total_points += sheet.get_earned_marks()
            max_points += sheet.get_total_max_marks()
        
        # Calculate average score as percentage
        if max_points > 0:
            avg_score = (total_points / max_points) * 100
        
        # Get the last signoff
        last_signoff = instructor_signoffs.order_by('-date_updated').first()
        
        # Get parts this instructor has signed off on
        signed_parts = Part.objects.filter(signoffs__instructor=instructor).distinct()
        signed_part_count = signed_parts.count()
        
        # Get labs this instructor has signed off parts for
        signed_labs = Lab.objects.filter(parts__in=signed_parts).distinct()
        signed_lab_count = signed_labs.count()
        
        stats = {
            'instructor': instructor,
            'total_signoffs': total_signoffs_count,
            'approved': approved_count,
            'rejected': rejected_count,
            'pending': pending_count,
            'signoffs_today': instructor_signoffs_today,
            'avg_score': avg_score,
            'last_signoff': last_signoff,
            'signed_part_count': signed_part_count,
            'signed_lab_count': signed_lab_count
        }
        
        instructor_stats.append(stats)
    
    # Sort by signoff count (descending)
    instructor_stats.sort(key=lambda x: x['total_signoffs'], reverse=True)
    
    return render(request, 'labs/reports/ta_report.html', {
        'instructor_stats': instructor_stats,
        'total_signoffs': total_signoffs,
        'signoffs_today': signoffs_today
    })

@login_required
def student_grade_report(request, student_id=None):
    """View detailed grade report for a student or all students."""
    # Check for CSV export format
    if request.GET.get('format') == 'csv':
        # Call the CSV export function
        return export_student_grade_csv(request, student_id)
        
    # Get all active students
    students = Student.objects.filter(active=True).order_by('name')
    
    # Filter to specific student if provided
    if student_id:
        students = students.filter(pk=student_id)
    
    # Get all labs
    labs = Lab.objects.all().order_by('name')
    
    # Build report data
    report_data = []
    
    for student in students:
        student_data = {
            'student': student,
            'labs': [],
            'earned_points': Decimal('0'),
            'total_points': Decimal('0'),
            'exceeds_requirements_count': 0  # Add counter for ER statuses
        }
        
        # Process each lab
        for lab in labs:
            lab_max_score = lab.get_max_score()
            lab_data = {
                'lab': lab,
                'parts': [],
                'earned_points': lab.get_student_score(student),
                'max_points': lab_max_score,
                'completion_percentage': lab.get_student_percentage(student),
                'letter_grade': lab.get_grade_letter(student)
            }
            
            # Add to student total
            student_data['earned_points'] += lab_data['earned_points']
            student_data['total_points'] += lab_max_score
            
            # Process each part in the lab
            for part in lab.parts.all().order_by('order'):
                part_status = part.get_part_status(student)
                
                part_data = {
                    'part': part,
                    'status': part_status,
                    'earned_points': Decimal('0'),
                    'max_points': part.get_max_score(),
                    'completion_percentage': Decimal('0'),
                    'possible_points': part.get_contribution_to_lab(),
                    'quality_scores': [],
                    'evaluation_sheet': None,
                    'quality_earned_points': Decimal('0'),
                    'quality_max_points': Decimal('0'),
                    'challenge_scores': [],
                    'challenge_earned_points': Decimal('0'),
                    'challenge_max_points': Decimal('0')
                }
                
                # Get signoff if it exists
                if part_status != 'not_started':
                    try:
                        signoff = Signoff.objects.get(student=student, part=part)
                        
                        # Get quality scores
                        quality_criteria = part.quality_criteria.all()
                        
                        for criteria in quality_criteria:
                            try:
                                score = QualityScore.objects.get(signoff=signoff, criteria=criteria)
                                weighted_score = score.weighted_score
                                max_weighted = criteria.max_points * criteria.weight
                            except QualityScore.DoesNotExist:
                                score = None
                                weighted_score = Decimal('0')
                                max_weighted = criteria.max_points * criteria.weight
                            
                            part_data['quality_scores'].append({
                                'criteria': criteria,
                                'score': score,
                                'weighted_score': weighted_score,
                                'max_weighted': Decimal(str(max_weighted))
                            })
                            
                            if score:
                                # Convert weighted_score to Decimal if it's a float
                                if isinstance(weighted_score, float):
                                    weighted_score = Decimal(str(weighted_score))
                                part_data['quality_earned_points'] += weighted_score
                            
                            part_data['quality_max_points'] += Decimal(str(max_weighted))
                        
                        # Get challenge scores if applicable
                        if part.has_challenges:
                            challenges = part.challenges.all().order_by('order')
                            
                            for challenge in challenges:
                                try:
                                    score = ChallengeScore.objects.get(signoff=signoff, challenge=challenge)
                                    part_data['challenge_scores'].append({
                                        'challenge': challenge,
                                        'score': score,
                                        'percentage': score.percentage
                                    })
                                    
                                    part_data['challenge_earned_points'] += Decimal(str(score.score))
                                except ChallengeScore.DoesNotExist:
                                    part_data['challenge_scores'].append({
                                        'challenge': challenge,
                                        'score': None,
                                        'percentage': 0
                                    })
                                    
                                # Add max points for this challenge
                                part_data['challenge_max_points'] += Decimal(str(challenge.max_points))
                        
                        # Get evaluation sheet if it exists
                        try:
                            eval_sheet = EvaluationSheet.objects.get(signoff=signoff)
                            
                            # Prepare evaluation data based on new rubric structure
                            if hasattr(eval_sheet, 'rubric') and eval_sheet.rubric:
                                eval_data = {}
                                
                                # Add data for each criterion in the rubric
                                for key, criterion in eval_sheet.rubric.criteria_data.items():
                                    status = eval_sheet.evaluations.get(key, 'ND')
                                    # Count "Exceeds Requirements" statuses
                                    if status == 'ER':
                                        student_data['exceeds_requirements_count'] += 1
                                    
                                    max_marks = Decimal(str(criterion['max_marks']))
                                    earned = max_marks * Decimal(str(EvaluationSheet.STATUS_TO_SCORE.get(status, 0)))
                                    
                                    eval_data[f"{key}_display"] = dict(EvaluationSheet.STATUS_CHOICES).get(status)
                                    eval_data[f"{key}_max_marks"] = max_marks
                                    eval_data[f"{key}_earned"] = earned
                                
                                # Add totals
                                eval_data['total_max_marks'] = eval_sheet.get_total_max_marks()
                                eval_data['total_earned_marks'] = eval_sheet.get_earned_marks()
                            else:
                                # Legacy system (this shouldn't execute after migration but keeping as fallback)
                                eval_data = {
                                    'total_max_marks': Decimal('0'),
                                    'total_earned_marks': Decimal('0')
                                }
                            
                            part_data['evaluation_sheet'] = eval_data
                            
                        except EvaluationSheet.DoesNotExist:
                            pass
                        
                        # Set earned points and completion percentage
                        if part_status == 'approved':
                            part_data['earned_points'] = signoff.get_total_quality_score()
                            if part_data['max_points'] > 0:
                                part_data['completion_percentage'] = (part_data['earned_points'] / part_data['max_points']) * 100
                    
                    except Signoff.DoesNotExist:
                        pass
                
                lab_data['parts'].append(part_data)
            
            student_data['labs'].append(lab_data)
        
        report_data.append(student_data)
    
    return render(request, 'labs/reports/student_grade_report.html', {
        'report_data': report_data,
        'labs': labs,
        'students': Student.objects.filter(active=True).order_by('name')
    })

@login_required
def quick_stats(request):
    """Get quick stats data."""
    # Count total approved signoffs
    total_signoffs = Signoff.objects.filter(status='approved').count()
    
    # Calculate average completion rate across students
    students = Student.objects.filter(active=True)
    if students.exists():
        completion_sum = 0
        for student in students:
            try:
                completion_sum += student.get_completion_status
            except Exception:
                pass
        avg_completion = round(completion_sum / students.count(), 1) if students.count() > 0 else 0
    else:
        avg_completion = 0
        
    # Count challenges and completed challenges
    total_challenges = Challenge.objects.count()
    # Use a more compatible way to count unique challenge completions
    challenge_scores = ChallengeScore.objects.filter(score__gt=0)
    completed_challenges = len(set([(score.challenge_id, score.signoff.student_id) for score in challenge_scores]))
    
    # Calculate more accurate challenge completion rate
    active_students = Student.objects.filter(active=True).count()
    if active_students > 0 and total_challenges > 0:
        # Total possible completions = active students * available challenges
        total_possible = active_students * total_challenges
        challenge_completion = round((completed_challenges / total_possible) * 100, 1)
    else:
        challenge_completion = 0
    
    # Set a mock value for exceeds requirements
    exceeds_requirements = 42
    
    # Get the grade distribution for the dashboard
    grade_distribution = {}
    # Initialize all grades to 0
    for grade in ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F']:
        grade_distribution[grade] = 0
    
    # Collect grade data - assign some mock data for testing
    # Set some random values for testing if data is correctly displayed
    grade_distribution = {
        'A+': 3, 'A': 5, 'A-': 7, 
        'B+': 10, 'B': 12, 'B-': 8, 
        'C+': 5, 'C': 4, 'C-': 3, 
        'D+': 2, 'D': 1, 'D-': 1, 
        'F': 0
    }
    
    # Set some mock data for testing challenge completion
    challenge_completion_by_student = {
        'not_attempted': 15,  # 0%
        'low': 8,             # <50%
        'medium': 12,         # 50-75%
        'high': 7,            # 75-90%
        'complete': 3         # >90%
    }
    
    return JsonResponse({
        'total_signoffs': total_signoffs,
        'avg_completion': avg_completion,
        'total_challenges': total_challenges,
        'completed_challenges': completed_challenges,
        'challenge_completion': challenge_completion,
        'exceeds_requirements': exceeds_requirements,
        'grade_distribution': grade_distribution,
        'challenge_completion_by_student': challenge_completion_by_student
    })

@login_required
def export_lab_csv(request, lab_id):
    """Export all student data for a lab as CSV with linearized criteria columns."""
    lab = get_object_or_404(Lab, pk=lab_id)
    students = Student.objects.filter(active=True).order_by('name')
    
    # Get grade scale info
    grade_scale_name = lab.grade_scale.name if lab.grade_scale else "Default Grade Scale"
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{lab.name}_grades.csv"'
    
    writer = csv.writer(response)
    
    # Write metadata header rows
    writer.writerow(['Lab', lab.name])
    writer.writerow(['Description', lab.description])
    writer.writerow(['Due Date', lab.due_date.strftime('%Y-%m-%d %H:%M')])
    writer.writerow(['Max Points (Calculated)', str(lab.get_max_score())])
    writer.writerow(['Total Points (Configured)', str(lab.total_points)])
    writer.writerow(['Grade Scale', grade_scale_name])
    writer.writerow([])  # Empty row as separator
    
    # Get all parts for this lab
    parts = lab.parts.all().order_by('order')
    
    # Collect all unique evaluation criteria from all parts
    all_criteria = set()
    for part in parts:
        # Get quality criteria for each part
        quality_criteria = part.quality_criteria.all()
        for criteria in quality_criteria:
            all_criteria.add(f"{part.name}_{criteria.name}")
        
        # For each part, check if there are any evaluation sheets with rubrics
        signoffs = Signoff.objects.filter(part=part)
        for signoff in signoffs:
            eval_sheets = signoff.evaluation_sheet.all()
            for sheet in eval_sheets:
                if hasattr(sheet, 'rubric') and sheet.rubric:
                    for criterion_key, criterion in sheet.rubric.criteria_data.items():
                        all_criteria.add(f"{part.name}_{criterion['name']}")
    
    # Create header row
    header = ['Student ID', 'Student Name', 'Email', 'Batch']
    
    # Add each part's status
    for part in parts:
        header.append(f"{part.name} Status")
    
    # Add each criteria
    header.extend(sorted(all_criteria))
    
    # Add total scores
    header.extend(['Total Score', 'Percentage', f'Letter Grade ({grade_scale_name})'])
    
    writer.writerow(header)
    
    # Write data for each student
    for student in students:
        row = [
            student.student_id,
            student.name,
            student.email,
            student.batch.strftime('%Y-%m-%d')
        ]
        
        # Add part status
        for part in parts:
            row.append(part.get_part_status(student))
        
        # Add criteria scores
        criteria_dict = {}
        for part in parts:
            # Get the student's signoff for this part
            try:
                signoff = Signoff.objects.get(student=student, part=part)
                
                # Add quality criteria scores
                quality_scores = signoff.quality_scores.all()
                for score in quality_scores:
                    criteria_key = f"{part.name}_{score.criteria.name}"
                    criteria_dict[criteria_key] = f"{score.score}/{score.criteria.max_points}"
                
                # Add evaluation rubric scores if available
                try:
                    eval_sheet = signoff.evaluation_sheet.first()
                    if eval_sheet and hasattr(eval_sheet, 'rubric') and eval_sheet.rubric:
                        for criterion_key, criterion in eval_sheet.rubric.criteria_data.items():
                            criteria_name = criterion['name']
                            key = f"{part.name}_{criteria_name}"
                            earned = eval_sheet.get_criterion_earned_marks(criterion_key)
                            max_marks = Decimal(str(criterion['max_marks']))
                            criteria_dict[key] = f"{earned}/{max_marks}"
                except:
                    pass
            except Signoff.DoesNotExist:
                pass
        
        # Add criteria data in the correct order
        for criteria_key in sorted(all_criteria):
            row.append(criteria_dict.get(criteria_key, "N/A"))
        
        # Add total scores
        max_score = lab.get_max_score()
        student_score = lab.get_student_score(student)
        row.append(f"{student_score}/{max_score}")
        row.append(f"{lab.get_student_percentage(student):.2f}%")
        row.append(lab.get_grade_letter(student))
        
        writer.writerow(row)
    
    # Add a separator row
    writer.writerow([])
    
    # Add grade scale information
    writer.writerow(['Grade Scale Information'])
    
    grade_scale = lab.grade_scale if lab.grade_scale else GradeScale.get_default_scale()
    writer.writerow(['Scale Name', grade_scale.name])
    writer.writerow(['Description', grade_scale.description])
    writer.writerow([])
    
    # Add grading thresholds
    writer.writerow(['Grade', 'Threshold (%)'])
    writer.writerow(['A+', f">= {grade_scale.a_plus_threshold}"])
    writer.writerow(['A', f">= {grade_scale.a_threshold}"])
    writer.writerow(['A-', f">= {grade_scale.a_minus_threshold}"])
    writer.writerow(['B+', f">= {grade_scale.b_plus_threshold}"])
    writer.writerow(['B', f">= {grade_scale.b_threshold}"])
    writer.writerow(['B-', f">= {grade_scale.b_minus_threshold}"])
    writer.writerow(['C+', f">= {grade_scale.c_plus_threshold}"])
    writer.writerow(['C', f">= {grade_scale.c_threshold}"])
    writer.writerow(['C-', f">= {grade_scale.c_minus_threshold}"])
    writer.writerow(['D+', f">= {grade_scale.d_plus_threshold}"])
    writer.writerow(['D', f">= {grade_scale.d_threshold}"])
    writer.writerow(['D-', f">= {grade_scale.d_minus_threshold}"])
    writer.writerow(['F', f"< {grade_scale.d_minus_threshold}"])
    
    return response


@login_required
def export_part_csv(request, part_id):
    """Export all student data for a specific part as CSV with linearized criteria columns."""
    part = get_object_or_404(Part, pk=part_id)
    students = Student.objects.filter(active=True).order_by('name')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{part.name}_grades.csv"'
    
    writer = csv.writer(response)
    
    # Get quality criteria for this part
    quality_criteria = part.quality_criteria.all()
    
    # Collect evaluation criteria from rubrics
    rubric_criteria = set()
    signoffs = Signoff.objects.filter(part=part)
    for signoff in signoffs:
        eval_sheets = signoff.evaluation_sheet.all()
        for sheet in eval_sheets:
            if hasattr(sheet, 'rubric') and sheet.rubric:
                for criterion_key, criterion in sheet.rubric.criteria_data.items():
                    rubric_criteria.add(criterion['name'])
    
    # Create header row
    header = ['Student ID', 'Student Name', 'Email', 'Batch', 'Status']
    
    # Add quality criteria columns
    for criteria in quality_criteria:
        header.append(f"Quality: {criteria.name}")
    
    # Add rubric criteria columns
    for criteria_name in sorted(rubric_criteria):
        header.append(f"Rubric: {criteria_name}")
    
    # Add total scores
    header.extend(['Quality Total', 'Percentage'])
    
    writer.writerow(header)
    
    # Write data for each student
    for student in students:
        row = [
            student.student_id,
            student.name,
            student.email,
            student.batch.strftime('%Y-%m-%d'),
            part.get_part_status(student)
        ]
        
        # Initialize scores dictionaries
        quality_scores_dict = {}
        rubric_scores_dict = {}
        
        # Get the student's signoff for this part
        try:
            signoff = Signoff.objects.get(student=student, part=part)
            
            # Add quality criteria scores
            quality_scores = signoff.quality_scores.all()
            for score in quality_scores:
                quality_scores_dict[score.criteria.name] = f"{score.score}/{score.criteria.max_points}"
            
            # Add evaluation rubric scores if available
            try:
                eval_sheet = signoff.evaluation_sheet.first()
                if eval_sheet and hasattr(eval_sheet, 'rubric') and eval_sheet.rubric:
                    for criterion_key, criterion in eval_sheet.rubric.criteria_data.items():
                        criteria_name = criterion['name']
                        earned = eval_sheet.get_criterion_earned_marks(criterion_key)
                        max_marks = Decimal(str(criterion['max_marks']))
                        rubric_scores_dict[criteria_name] = f"{earned}/{max_marks}"
            except:
                pass
                
            # Add quality criteria data in the correct order
            for criteria in quality_criteria:
                row.append(quality_scores_dict.get(criteria.name, "N/A"))
            
            # Add rubric criteria data in the correct order
            for criteria_name in sorted(rubric_criteria):
                row.append(rubric_scores_dict.get(criteria_name, "N/A"))
            
            # Add total scores
            max_score = part.get_max_score()
            student_score = part.get_student_score(student)
            row.append(f"{student_score}/{max_score}")
            row.append(f"{part.get_student_percentage(student):.2f}%")
            
        except Signoff.DoesNotExist:
            # If no signoff exists, add N/A for all criteria
            for _ in range(len(quality_criteria) + len(rubric_criteria) + 2):
                row.append("N/A")
        
        writer.writerow(row)
    
    return response


@login_required
def export_student_grade_csv(request, student_id=None):
    """Export comprehensive student grade data as CSV with linearized columns."""
    # Get all active students
    students = Student.objects.filter(active=True).order_by('name')
    
    # Filter to specific student if provided
    if student_id:
        students = students.filter(pk=student_id)
    
    # Get all labs
    labs = Lab.objects.all().order_by('name')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    filename = "student_grades.csv"
    if student_id and students.exists():
        student = students.first()
        filename = f"{student.name}_{student.student_id}_grades.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    
    # Build a comprehensive list of all criteria across all parts
    all_quality_criteria = []
    all_rubric_criteria = set()
    all_challenges = []
    
    # Organize labs and parts data
    lab_parts = {}
    
    for lab in labs:
        parts = lab.parts.all().order_by('order')
        lab_parts[lab.id] = parts
        
        for part in parts:
            # Get quality criteria
            quality_criteria = part.quality_criteria.all()
            for criteria in quality_criteria:
                all_quality_criteria.append((lab.name, part.name, criteria.name, criteria.id))
            
            # Get challenges if the part has them
            if part.has_challenges:
                challenges = part.challenges.all()
                for challenge in challenges:
                    all_challenges.append((lab.name, part.name, challenge.name, challenge.id))
            
            # Get rubric criteria
            signoffs = Signoff.objects.filter(part=part)
            for signoff in signoffs:
                eval_sheets = signoff.evaluation_sheet.all()
                for sheet in eval_sheets:
                    if hasattr(sheet, 'rubric') and sheet.rubric:
                        for criterion_key, criterion in sheet.rubric.criteria_data.items():
                            all_rubric_criteria.add((lab.name, part.name, criterion['name'], criterion_key))
    
    # Sort criteria lists
    all_quality_criteria.sort()
    all_rubric_criteria = sorted(all_rubric_criteria)
    all_challenges.sort()
    
    # Create header row
    header = ['Student ID', 'Student Name', 'Email', 'Batch']
    
    # Add lab and part status columns
    for lab in labs:
        parts = lab_parts[lab.id]
        # Include grade scale information
        grade_scale_name = lab.grade_scale.name if lab.grade_scale else "Default"
        header.append(f"{lab.name} - Grade ({grade_scale_name})")
        header.append(f"{lab.name} - Percentage")
        
        for part in parts:
            header.append(f"{lab.name} - {part.name} - Status")
    
    # Add quality criteria columns
    for lab_name, part_name, criteria_name, _ in all_quality_criteria:
        header.append(f"{lab_name} - {part_name} - Quality: {criteria_name}")
    
    # Add challenge columns
    for lab_name, part_name, challenge_name, _ in all_challenges:
        header.append(f"{lab_name} - {part_name} - Challenge: {challenge_name}")
    
    # Add rubric criteria columns
    for lab_name, part_name, criteria_name, _ in all_rubric_criteria:
        header.append(f"{lab_name} - {part_name} - Rubric: {criteria_name}")
    
    # Add overall score
    default_scale = GradeScale.get_default_scale()
    header.append('Overall Score')
    header.append('Overall Percentage')
    header.append(f'Overall Grade ({default_scale.name})')
    
    writer.writerow(header)
    
    # Write data for each student
    for student in students:
        row = [
            student.student_id,
            student.name,
            student.email,
            student.batch.strftime('%Y-%m-%d')
        ]
        
        # Collect all scores in dictionaries
        lab_data = {}
        part_status = {}
        quality_scores = {}
        challenge_scores = {}
        rubric_scores = {}
        
        # Process each lab and its parts
        for lab in labs:
            parts = lab_parts[lab.id]
            
            # Add lab grade data
            lab_data[lab.id] = {
                'grade': lab.get_grade_letter(student),
                'percentage': lab.get_student_percentage(student)
            }
            
            # Process each part
            for part in parts:
                status = part.get_part_status(student)
                part_status[(lab.id, part.id)] = status
                
                # If part has been started, collect score data
                if status != 'not_started':
                    try:
                        signoff = Signoff.objects.get(student=student, part=part)
                        
                        # Collect quality scores
                        quality_criteria = part.quality_criteria.all()
                        for criteria in quality_criteria:
                            try:
                                score = QualityScore.objects.get(signoff=signoff, criteria=criteria)
                                quality_scores[(lab.id, part.id, criteria.id)] = {
                                    'score': score.score,
                                    'max_points': criteria.max_points
                                }
                            except QualityScore.DoesNotExist:
                                pass
                        
                        # Collect challenge scores if applicable
                        if part.has_challenges:
                            challenges = part.challenges.all()
                            for challenge in challenges:
                                try:
                                    score = ChallengeScore.objects.get(signoff=signoff, challenge=challenge)
                                    challenge_scores[(lab.id, part.id, challenge.id)] = {
                                        'score': score.score,
                                        'max_points': challenge.max_points
                                    }
                                except ChallengeScore.DoesNotExist:
                                    pass
                        
                        # Collect rubric scores
                        try:
                            eval_sheet = signoff.evaluation_sheet.first()
                            if eval_sheet and hasattr(eval_sheet, 'rubric') and eval_sheet.rubric:
                                for criterion_key, criterion in eval_sheet.rubric.criteria_data.items():
                                    status = eval_sheet.evaluations.get(criterion_key, 'ND')
                                    earned = eval_sheet.get_criterion_earned_marks(criterion_key)
                                    max_marks = Decimal(str(criterion['max_marks']))
                                    
                                    rubric_scores[(lab.id, part.id, criterion_key)] = {
                                        'earned': earned,
                                        'max_marks': max_marks,
                                        'status': status
                                    }
                        except:
                            pass
                            
                    except Signoff.DoesNotExist:
                        pass
        
        # Add lab grades and part status to row
        for lab in labs:
            parts = lab_parts[lab.id]
            
            # Add lab grade
            lab_grade_data = lab_data.get(lab.id, {'grade': 'F', 'percentage': 0})
            row.append(lab_grade_data['grade'])
            row.append(f"{lab_grade_data['percentage']:.2f}%")
            
            # Add part status
            for part in parts:
                status = part_status.get((lab.id, part.id), 'not_started')
                row.append(status)
        
        # Add quality criteria scores
        for lab_name, part_name, criteria_name, criteria_id in all_quality_criteria:
            # Find the lab and part IDs
            lab_id = next((lab.id for lab in labs if lab.name == lab_name), None)
            if lab_id:
                parts = lab_parts[lab_id]
                part_id = next((part.id for part in parts if part.name == part_name), None)
                
                if part_id:
                    score_data = quality_scores.get((lab_id, part_id, criteria_id), None)
                    if score_data:
                        row.append(f"{score_data['score']}/{score_data['max_points']}")
                    else:
                        row.append("N/A")
                else:
                    row.append("N/A")
            else:
                row.append("N/A")
        
        # Add challenge scores
        for lab_name, part_name, challenge_name, challenge_id in all_challenges:
            # Find the lab and part IDs
            lab_id = next((lab.id for lab in labs if lab.name == lab_name), None)
            if lab_id:
                parts = lab_parts[lab_id]
                part_id = next((part.id for part in parts if part.name == part_name), None)
                
                if part_id:
                    score_data = challenge_scores.get((lab_id, part_id, challenge_id), None)
                    if score_data:
                        row.append(f"{score_data['score']}/{score_data['max_points']}")
                    else:
                        row.append("N/A")
                else:
                    row.append("N/A")
            else:
                row.append("N/A")
        
        # Add rubric criteria scores
        for lab_name, part_name, criteria_name, criterion_key in all_rubric_criteria:
            # Find the lab and part IDs
            lab_id = next((lab.id for lab in labs if lab.name == lab_name), None)
            if lab_id:
                parts = lab_parts[lab_id]
                part_id = next((part.id for part in parts if part.name == part_name), None)
                
                if part_id:
                    score_data = rubric_scores.get((lab_id, part_id, criterion_key), None)
                    if score_data:
                        row.append(f"{score_data['earned']}/{score_data['max_marks']} ({dict(EvaluationSheet.STATUS_CHOICES).get(score_data['status'], 'ND')})")
                    else:
                        row.append("N/A")
                else:
                    row.append("N/A")
            else:
                row.append("N/A")
        
        # Add overall scores calculated from student model
        overall_grade = student.get_overall_grade()
        row.append(f"{student_data['earned_points']}/{student_data['total_points']}")  # Raw points
        row.append(f"{overall_grade:.2f}%")  # Percentage
        row.append(student.get_course_letter_grade())  # Letter grade
        
        writer.writerow(row)
    
    return response