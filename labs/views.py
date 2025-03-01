from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from .models import *
from .forms import StudentUploadForm, UserRoleForm
from django.shortcuts import render, redirect, reverse
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test, login_required
from django.db.models import Count, Avg, Sum, F, Q, Case, When, Value
import datetime
import pandas as pd
from io import BytesIO
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied

# Define role check decorators
def instructor_required(function):
    """Decorator to check if user is an instructor."""
    def wrap(request, *args, **kwargs):
        try:
            if hasattr(request.user, 'role') and request.user.role.role == 'instructor':
                return function(request, *args, **kwargs)
            else:
                raise PermissionDenied("You must be an instructor to access this page.")
        except (AttributeError, UserRole.DoesNotExist):
            raise PermissionDenied("You must be an instructor to access this page.")
    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap

def ta_or_instructor_required(function):
    """Decorator to check if user is a TA or instructor."""
    def wrap(request, *args, **kwargs):
        try:
            if hasattr(request.user, 'role') and request.user.role.role in ['instructor', 'ta']:
                return function(request, *args, **kwargs)
            else:
                raise PermissionDenied("You must be a TA or instructor to access this page.")
        except (AttributeError, UserRole.DoesNotExist):
            raise PermissionDenied("You must be a TA or instructor to access this page.")
    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap

# Student Management Views
@login_required
@instructor_required
def student_list(request):
    """View to list all students with pagination and search."""
    search_query = request.GET.get('search', '')
    active_filter = request.GET.get('active', 'all')
    
    students = Student.objects.all()
    
    # Apply search filter
    if search_query:
        students = students.filter(
            Q(student_id__icontains=search_query) | 
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    # Apply active filter
    if active_filter == 'active':
        students = students.filter(active=True)
    elif active_filter == 'inactive':
        students = students.filter(active=False)
    
    # Stats
    total_students = students.count()
    active_students = students.filter(active=True).count()
    inactive_students = total_students - active_students
    
    context = {
        'students': students,
        'search_query': search_query,
        'active_filter': active_filter,
        'total_students': total_students,
        'active_students': active_students,
        'inactive_students': inactive_students,
    }
    
    return render(request, 'labs/student_list.html', context)

@login_required
@instructor_required
def student_upload(request):
    """View to upload students from Excel file."""
    if request.method == 'POST':
        form = StudentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['excel_file']
            
            try:
                # Read the Excel file into a pandas DataFrame
                df = pd.read_excel(excel_file)
                
                # Check required columns
                required_columns = ['student_id', 'name', 'email', 'batch']
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    messages.error(request, f"Missing required columns: {', '.join(missing_columns)}")
                    return render(request, 'labs/student_upload.html', {'form': form})
                
                # Initialize counters
                created_count = 0
                updated_count = 0
                error_count = 0
                errors = []
                
                # Process each row
                for index, row in df.iterrows():
                    try:
                        # Convert the batch date
                        try:
                            batch_date = pd.to_datetime(row['batch']).date()
                        except (ValueError, TypeError):
                            errors.append(f"Row {index+2}: Invalid batch date format for {row['student_id']}")
                            error_count += 1
                            continue
                        
                        # Create or update student
                        student, created = Student.objects.update_or_create(
                            student_id=row['student_id'],
                            defaults={
                                'name': row['name'],
                                'email': row['email'],
                                'batch': batch_date,
                                'active': True  # Default to active
                            }
                        )
                        
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1
                            
                    except Exception as e:
                        errors.append(f"Row {index+2}: Error processing {row['student_id']} - {str(e)}")
                        error_count += 1
                
                # Set messages
                messages.success(request, f"Successfully processed {created_count + updated_count} students ({created_count} created, {updated_count} updated)")
                
                if error_count > 0:
                    messages.warning(request, f"{error_count} errors occurred during import. See details below.")
                    for error in errors:
                        messages.warning(request, error)
                
                return redirect('labs:student_list')
                
            except Exception as e:
                messages.error(request, f"Error processing Excel file: {str(e)}")
        
    else:
        form = StudentUploadForm()
    
    return render(request, 'labs/student_upload.html', {'form': form})

@login_required
@instructor_required
def student_toggle_active(request, student_id):
    """Toggle a student's active status."""
    student = get_object_or_404(Student, id=student_id)
    student.active = not student.active
    student.save()
    
    messages.success(request, f"Student {student.name} ({student.student_id}) has been {'activated' if student.active else 'deactivated'}")
    return redirect('labs:student_list')

# User Management Views
@login_required
@instructor_required
def user_list(request):
    """View to list all users and their roles."""
    users = User.objects.all().order_by('username')
    
    # Add role information to each user
    for user in users:
        try:
            user.role_info = user.role
        except UserRole.DoesNotExist:
            user.role_info = None
    
    context = {
        'users': users,
    }
    
    return render(request, 'labs/user_list.html', context)

@login_required
@instructor_required
def user_create(request):
    """View to create a new user with role."""
    if request.method == 'POST':
        form = UserRoleForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password1']
            
            # Check if username already exists
            if User.objects.filter(username=username).exists():
                form.add_error('username', "Username already exists")
                return render(request, 'labs/user_form.html', {'form': form, 'title': 'Create User'})
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name']
            )
            
            # Create role
            role = form.save(commit=False)
            role.user = user
            role.save()
            
            messages.success(request, f"User {username} created successfully with role {role.get_role_display()}")
            return redirect('labs:user_list')
    else:
        form = UserRoleForm()
    
    return render(request, 'labs/user_form.html', {'form': form, 'title': 'Create User'})

@login_required
@instructor_required
def user_edit(request, user_id):
    """View to edit an existing user and their role."""
    user = get_object_or_404(User, id=user_id)
    
    # Get or create role
    try:
        role = user.role
    except UserRole.DoesNotExist:
        role = UserRole(user=user)
    
    if request.method == 'POST':
        form = UserRoleForm(request.POST, instance=role)
        if form.is_valid():
            # Update user info
            user.username = form.cleaned_data['username']
            user.email = form.cleaned_data['email']
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            
            # Update password if provided
            if form.cleaned_data['password1']:
                user.set_password(form.cleaned_data['password1'])
            
            user.save()
            
            # Save role
            role = form.save()
            
            messages.success(request, f"User {user.username} updated successfully")
            return redirect('labs:user_list')
    else:
        # Prepopulate form
        form = UserRoleForm(instance=role, initial={
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
        })
    
    return render(request, 'labs/user_form.html', {'form': form, 'title': 'Edit User'})

# Batch Operations
@login_required
@instructor_required
def batch_toggle_students(request):
    """Toggle active status for multiple students at once."""
    if request.method == 'POST':
        action = request.POST.get('action')
        batch_date = request.POST.get('batch_date')
        student_ids = request.POST.getlist('student_ids')
        
        if not (action and (batch_date or student_ids)):
            messages.error(request, "Please select an action and either a batch date or specific students.")
            return redirect('labs:student_list')
        
        # Initialize query for students
        students_query = Student.objects.all()
        
        # Filter by batch date if provided
        if batch_date:
            try:
                batch_date = datetime.datetime.strptime(batch_date, '%Y-%m-%d').date()
                students_query = students_query.filter(batch=batch_date)
            except ValueError:
                messages.error(request, "Invalid batch date format. Use YYYY-MM-DD.")
                return redirect('labs:student_list')
        
        # Filter by specific student IDs if provided
        if student_ids:
            students_query = students_query.filter(id__in=student_ids)
        
        # Apply the action
        count = 0
        if action == 'activate':
            count = students_query.update(active=True)
            messages.success(request, f"Successfully activated {count} students.")
        elif action == 'deactivate':
            count = students_query.update(active=False)
            messages.success(request, f"Successfully deactivated {count} students.")
        else:
            messages.error(request, "Invalid action.")
            
        return redirect('labs:student_list')
    
    # If GET request, show the form
    batches = Student.objects.dates('batch', 'day', order='DESC')
    students = Student.objects.all().order_by('name')
    
    context = {
        'batches': batches,
        'students': students,
    }
    
    return render(request, 'labs/batch_toggle_students.html', context)

# Report Generation
@login_required
def student_grade_report(request, student_id=None):
    """Generate detailed grade report for a student."""
    if student_id:
        student = get_object_or_404(Student, id=student_id)
        students = [student]
    else:
        # If no student_id, get all active students
        students = Student.objects.filter(active=True).order_by('name')
    
    # Format for reports
    report_format = request.GET.get('format', 'html')
    
    # Build report data
    report_data = []
    for student in students:
        student_data = {
            'student': student,
            'labs': []
        }
        
        # Get all labs
        labs = Lab.objects.all().order_by('due_date')
        
        total_points = 0
        earned_points = 0
        
        for lab in labs:
            lab_data = {
                'lab': lab,
                'parts': [],
                'total_points': lab.total_points,
                'earned_points': 0,
                'completion_percentage': 0
            }
            
            # Get all parts for this lab
            parts = Part.objects.filter(lab=lab).order_by('order')
            
            for part in parts:
                # Get signoff for this student and part
                try:
                    signoff = Signoff.objects.get(student=student, part=part)
                    status = signoff.status
                    
                    # Calculate quality scores
                    quality_scores = []
                    part_points = 0
                    max_part_points = 0
                    
                    for criteria in QualityCriteria.objects.filter(part=part):
                        try:
                            score = QualityScore.objects.get(signoff=signoff, criteria=criteria)
                            weighted_score = float(score.weighted_score) * float(lab.total_points)
                            max_weighted = float(criteria.weight) * float(lab.total_points)
                            
                            quality_scores.append({
                                'criteria': criteria,
                                'score': score,
                                'weighted_score': weighted_score,
                                'max_weighted': max_weighted
                            })
                            
                            part_points += weighted_score
                            max_part_points += max_weighted
                        except QualityScore.DoesNotExist:
                            quality_scores.append({
                                'criteria': criteria,
                                'score': None,
                                'weighted_score': 0,
                                'max_weighted': float(criteria.weight) * float(lab.total_points)
                            })
                            max_part_points += float(criteria.weight) * float(lab.total_points)
                    
                except Signoff.DoesNotExist:
                    status = 'not_started'
                    quality_scores = []
                    part_points = 0
                    # Calculate max possible points for this part
                    max_part_points = sum(float(c.weight) for c in QualityCriteria.objects.filter(part=part)) * float(lab.total_points)
                
                # Part data with points
                part_data = {
                    'part': part,
                    'status': status,
                    'quality_scores': quality_scores,
                    'earned_points': part_points if status == 'approved' else 0,
                    'max_points': max_part_points,
                    'completion_percentage': (float(part_points) / float(max_part_points) * 100) if max_part_points > 0 and status == 'approved' else 0
                }
                
                lab_data['parts'].append(part_data)
                lab_data['earned_points'] += part_data['earned_points']
            
            # Calculate lab completion percentage
            if lab_data['total_points'] > 0:
                lab_data['completion_percentage'] = (float(lab_data['earned_points']) / float(lab_data['total_points'])) * 100
            
            student_data['labs'].append(lab_data)
            total_points += lab.total_points
            earned_points += lab_data['earned_points']
        
        # Calculate overall grade percentage
        student_data['total_points'] = total_points
        student_data['earned_points'] = earned_points
        student_data['grade_percentage'] = (float(earned_points) / float(total_points) * 100) if total_points > 0 else 0
        
        report_data.append(student_data)
    
    context = {
        'report_data': report_data,
        'single_student': student_id is not None
    }
    
    # Handle different output formats
    if report_format == 'csv':
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="student_grades.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Student ID', 'Student Name', 'Email', 'Overall Grade %', 'Total Points', 'Earned Points'])
        
        for student_data in report_data:
            writer.writerow([
                student_data['student'].student_id,
                student_data['student'].name,
                student_data['student'].email,
                f"{student_data['grade_percentage']:.2f}",
                student_data['total_points'],
                student_data['earned_points']
            ])
            
            # Add blank row for readability
            writer.writerow([])
            
            # Add lab-specific data
            for lab_data in student_data['labs']:
                writer.writerow(['Lab', lab_data['lab'].name, 'Completion %', f"{lab_data['completion_percentage']:.2f}", 'Points', f"{lab_data['earned_points']:.2f}/{lab_data['total_points']}"])
                
                # Add part-specific data
                for part_data in lab_data['parts']:
                    writer.writerow(['', 'Part', part_data['part'].name, 'Status', part_data['status'], f"{part_data['earned_points']:.2f}/{part_data['max_points']:.2f}"])
                    
                    # Add quality criteria data
                    for quality in part_data['quality_scores']:
                        if quality['score']:
                            writer.writerow(['', '', 'Quality', quality['criteria'].name, f"{quality['score'].score}/{quality['criteria'].max_points}", f"{quality['weighted_score']:.2f}/{quality['max_weighted']:.2f}"])
            
            writer.writerow([])  # Extra space between students
        
        return response
    
    elif report_format == 'pdf':
        # This is a placeholder for PDF generation
        # In a real implementation, you would use a library like ReportLab or WeasyPrint
        messages.warning(request, "PDF generation is not yet implemented. Showing HTML version instead.")
        return render(request, 'labs/reports/student_grade_report.html', context)
    
    # Default to HTML format
    return render(request, 'labs/reports/student_grade_report.html', context)

# Dashboard View
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
    ).values('id', 'name', 'student_id', 'email')[:10]  # Limit to 10 results
    print(students)
    
    return JsonResponse({'students': list(students)})

@login_required
def get_existing_signoff(request):
    """AJAX view to get existing signoffs for a student and lab."""
    student_id = request.GET.get('student_id', '')
    lab_id = request.GET.get('lab_id', '')

    if not student_id or not lab_id:
        return JsonResponse([], safe=False)
    
    try:
        # First get the student object
        student = Student.objects.get(student_id=student_id)
        
        # Get all parts for the lab
        parts = Part.objects.filter(lab_id=lab_id)
        part_ids = [part.id for part in parts]
        
        # Get signoffs for this student and these parts
        signoffs = Signoff.objects.filter(
            student=student,
            part_id__in=part_ids
        ).select_related('part').values(
            'id', 'part_id', 'status', 'comments', 'date_updated'
        )
        
        return JsonResponse(list(signoffs), safe=False)
    except Student.DoesNotExist:
        return JsonResponse([], safe=False)


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
    
    try:
        part = Part.objects.get(id=part_id)
        criteria = list(QualityCriteria.objects.filter(part_id=part_id).values('id', 'name', 'max_points', 'weight'))
        
        # If no custom criteria are defined for this part, use default criteria
        if not criteria:
            # Default criteria for all parts if none specified
            criteria = [
                {'id': f'default_1_{part_id}', 'name': 'SPLD code', 'max_points': 10, 'weight': 1.0},
                {'id': f'default_2_{part_id}', 'name': 'Assembly Language Code Style', 'max_points': 10, 'weight': 1.0},
                {'id': f'default_3_{part_id}', 'name': 'Required Elements functionality', 'max_points': 10, 'weight': 1.0},
                {'id': f'default_4_{part_id}', 'name': 'Sign-off done without excessive retries', 'max_points': 10, 'weight': 1.0},
                {'id': f'default_5_{part_id}', 'name': 'Student understanding and skills', 'max_points': 10, 'weight': 1.0},
            ]
        
        return JsonResponse(criteria, safe=False)
    except Part.DoesNotExist:
        return JsonResponse([], safe=False)
    
    
    
@login_required
def get_signoff_details(request):
    """AJAX view to get detailed information about a signoff."""
    student_id = request.GET.get('student_id', '')
    part_id = request.GET.get('part_id', '')
    
    if not student_id or not part_id:
        return JsonResponse({'found': False})
    
    try:
        # Get the student object
        student = Student.objects.get(student_id=student_id)
        
        # Get the signoff
        signoff = Signoff.objects.filter(
            student=student,
            part_id=part_id
        ).select_related('part', 'instructor').first()
        
        if not signoff:
            return JsonResponse({'found': False})
        
        # Get the history of this signoff
        history = Signoff.objects.filter(
            student=student,
            part_id=part_id
        ).order_by('-date_updated').values(
            'status', 'comments', 'date_updated', 'instructor__username'
        )
            
        # Prepare response
        response = {
            'found': True,
            'id': signoff.id,
            'status': signoff.status,
            'comments': signoff.comments,
            'date_updated': signoff.date_updated.isoformat(),
            'overall_score': 2,  # Default to "Meets Requirements"
            'quality_scores': [],
            'history': list(history)
        }
        
        return JsonResponse(response)
    except Student.DoesNotExist:
        return JsonResponse({'found': False})

@login_required
def quick_signoff_submit(request):
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
    default_criteria_processed = set()  # Track which default criteria were processed
    
    for key, value in request.POST.items():
        if key.startswith('criteria_'):
            parts = key.split('_')
            if len(parts) < 2:
                continue
                
            criteria_id = parts[1]
            
            # Check if it's a default criteria (from the format default_X_partid)
            if criteria_id.startswith('default_'):
                default_criteria_processed.add(criteria_id)
                # For default criteria, create or get a QualityCriteria object
                criteria_name = None
                if criteria_id.startswith('default_1_'):
                    criteria_name = 'SPLD code'
                elif criteria_id.startswith('default_2_'):
                    criteria_name = 'Assembly Language Code Style'
                elif criteria_id.startswith('default_3_'):
                    criteria_name = 'Required Elements functionality'
                elif criteria_id.startswith('default_4_'):
                    criteria_name = 'Sign-off done without excessive retries'
                elif criteria_id.startswith('default_5_'):
                    criteria_name = 'Student understanding and skills'
                
                if criteria_name:
                    # Create or get the criteria
                    criteria, _ = QualityCriteria.objects.get_or_create(
                        part=part,
                        name=criteria_name,
                        defaults={'max_points': 10, 'weight': 1.0}
                    )
                    
                    # Convert radio value to points based on criteria's max_points
                    value_map = {
                        '0': 0,                               # Not Applicable
                        '1': int(criteria.max_points * 0.25),  # Poor/Not Complete - 25%
                        '2': int(criteria.max_points * 0.5),   # Meets Requirements - 50%
                        '3': int(criteria.max_points * 0.75),  # Exceeds Requirements - 75%
                        '4': criteria.max_points              # Outstanding - 100%
                    }
                    score = value_map.get(value, 0)
                    
                    # Create or update score
                    QualityScore.objects.update_or_create(
                        signoff=signoff,
                        criteria=criteria,
                        defaults={'score': score}
                    )
            else:
                # Regular criteria processing
                try:
                    criteria = QualityCriteria.objects.get(id=criteria_id)
                    
                    # Convert radio value to points based on criteria's max_points
                    value_map = {
                        '0': 0,                               # Not Applicable
                        '1': int(criteria.max_points * 0.25),  # Poor/Not Complete - 25%
                        '2': int(criteria.max_points * 0.5),   # Meets Requirements - 50%
                        '3': int(criteria.max_points * 0.75),  # Exceeds Requirements - 75%
                        '4': criteria.max_points              # Outstanding - 100%
                    }
                    score = value_map.get(value, 0)
                    
                    # Create or update score
                    QualityScore.objects.update_or_create(
                        signoff=signoff,
                        criteria=criteria,
                        defaults={'score': score}
                    )
                except QualityCriteria.DoesNotExist:
                    continue
    
    return JsonResponse({
        'success': True, 
        'message': f"Signoff {'created' if created else 'updated'} successfully",
        'signoff_id': signoff.id,
        'status': status
    })
    
    
def lab_list(request):
    labs = Lab.objects.all()
    return render(request, "labs/lablist.html", context={'labs': labs})
    
    
# Report Views
@login_required
def reports(request):
    """Main reports dashboard."""
    labs = Lab.objects.all()
    students = Student.objects.filter(active=True)
    
    report_types = [
        {'id': 'lab_report', 'name': 'Lab Completion Report', 'description': 'View progress by lab'},
        {'id': 'student_report', 'name': 'Student Progress Report', 'description': 'View progress by student'},
        {'id': 'ta_report', 'name': 'TA Grading Report', 'description': 'View signoffs by instructor'},
        {'id': 'grade_report', 'name': 'Student Grade Report', 'description': 'View detailed grades with quality scores'},
    ]
    
    context = {
        'labs': labs,
        'students': students,
        'report_types': report_types,
    }
    
    return render(request, "labs/reports/dashboard.html", context)

@login_required
def lab_report(request, lab_id=None):
    """Report showing completion status for a specific lab."""
    try:
        if lab_id:
            lab = Lab.objects.get(id=lab_id)
        else:
            lab = Lab.objects.first()
            if not lab:
                return render(request, "labs/reports/no_data.html", {'message': 'No labs found'})
        
        # Get parts for this lab
        parts = Part.objects.filter(lab=lab).order_by('order')
        
        # Get all students
        students = Student.objects.filter(active=True).order_by('name')
        
        # Build a matrix of student completions
        matrix = []
        
        for student in students:
            row = {'student': student, 'parts': []}
            
            # Get signoffs for this student
            signoffs = Signoff.objects.filter(
                student=student,
                part__lab=lab
            ).values('part_id', 'status')
            
            # Convert to dict for easier lookup
            signoff_dict = {s['part_id']: s['status'] for s in signoffs}
            
            # Add part status for each part
            for part in parts:
                status = signoff_dict.get(part.id, 'not_started')
                row['parts'].append({
                    'part': part,
                    'status': status,
                    'css_class': get_status_css_class(status)
                })
            
            # Calculate completion percentage
            required_parts = sum(1 for part in parts if part.is_required)
            if required_parts > 0:
                approved_required = sum(1 for part in parts if part.is_required and 
                                       signoff_dict.get(part.id) == 'approved')
                row['completion'] = (approved_required / required_parts) * 100
            else:
                row['completion'] = 0
                
            matrix.append(row)
        
        # Calculate overall statistics
        stats = {
            'total_students': students.count(),
            'completed': sum(1 for row in matrix if row['completion'] >= 100),
            'started': sum(1 for row in matrix if 0 < row['completion'] < 100),
            'not_started': sum(1 for row in matrix if row['completion'] == 0),
        }
        
        if stats['total_students'] > 0:
            stats['completion_percent'] = (stats['completed'] / stats['total_students']) * 100
        else:
            stats['completion_percent'] = 0
        
        # Other available labs for report switching
        other_labs = Lab.objects.exclude(id=lab.id)
        
        context = {
            'lab': lab,
            'parts': parts,
            'matrix': matrix,
            'stats': stats,
            'other_labs': other_labs,
        }
        
        return render(request, "labs/reports/lab_report.html", context)
    
    except Lab.DoesNotExist:
        return render(request, "labs/reports/no_data.html", {'message': 'Lab not found'})

@login_required
def student_progress_report(request):
    """Report showing progress for all students across all labs."""
    students = Student.objects.filter(active=True).order_by('name')
    labs = Lab.objects.all().order_by('due_date')
    
    # Get all required parts for each lab
    lab_parts = {}
    for lab in labs:
        required_parts = Part.objects.filter(lab=lab, is_required=True).count()
        lab_parts[lab.id] = required_parts
    
    # Build matrix of student progress
    matrix = []
    
    for student in students:
        row = {'student': student, 'labs': []}
        
        for lab in labs:
            # Get approved signoffs for this student and lab
            approved_signoffs = Signoff.objects.filter(
                student=student,
                part__lab=lab,
                part__is_required=True,
                status='approved'
            ).count()
            
            # Calculate completion percentage
            required_parts = lab_parts[lab.id]
            if required_parts > 0:
                completion = (approved_signoffs / required_parts) * 100
            else:
                completion = 0
                
            # Add lab status to row
            row['labs'].append({
                'lab': lab,
                'completion': completion,
                'css_class': get_completion_css_class(completion)
            })
        
        # Calculate overall completion across all labs
        total_required = sum(lab_parts.values())
        total_completed = Signoff.objects.filter(
            student=student,
            part__is_required=True,
            status='approved'
        ).count()
        
        if total_required > 0:
            row['overall_completion'] = (total_completed / total_required) * 100
        else:
            row['overall_completion'] = 0
            
        matrix.append(row)
    
    # Overall stats
    stats = {
        'total_students': students.count(),
        'fully_completed': sum(1 for row in matrix if row['overall_completion'] >= 100),
    }
    
    if stats['total_students'] > 0:
        stats['overall_completion'] = sum(row['overall_completion'] for row in matrix) / stats['total_students']
    else:
        stats['overall_completion'] = 0
    
    context = {
        'students': students,
        'labs': labs,
        'matrix': matrix,
        'stats': stats,
    }
    
    return render(request, "labs/reports/student_progress.html", context)

@login_required
def ta_report(request):
    """Report showing signoffs by instructor."""
    # Get all instructors who have done signoffs
    instructors = User.objects.filter(taken_signoffs__isnull=False).distinct()
    
    # Get stats for each instructor
    instructor_stats = []
    
    for instructor in instructors:
        signoffs = Signoff.objects.filter(instructor=instructor)
        
        stats = {
            'instructor': instructor,
            'total_signoffs': signoffs.count(),
            'approved': signoffs.filter(status='approved').count(),
            'rejected': signoffs.filter(status='rejected').count(),
            'pending': signoffs.filter(status='pending').count(),
            'last_signoff': signoffs.order_by('-date_updated').first(),
        }
        
        # Calculate average scores for this instructor
        quality_scores = QualityScore.objects.filter(signoff__instructor=instructor)
        if quality_scores.exists():
            avg_score = quality_scores.aggregate(
                avg=models.Avg(models.F('score') / models.F('criteria__max_points'))
            )['avg'] or 0
            stats['avg_score'] = avg_score * 100  # Convert to percentage
        else:
            stats['avg_score'] = 0
            
        instructor_stats.append(stats)
    
    # Sort by number of signoffs
    instructor_stats.sort(key=lambda x: x['total_signoffs'], reverse=True)
    
    # Overall stats
    total_signoffs = Signoff.objects.count()
    signoffs_today = Signoff.objects.filter(
        date_updated__date=datetime.datetime.now().date()
    ).count()
    
    context = {
        'instructor_stats': instructor_stats,
        'total_signoffs': total_signoffs,
        'signoffs_today': signoffs_today,
    }
    
    return render(request, "labs/reports/ta_report.html", context)

@login_required
def quick_stats(request):
    """AJAX endpoint for quick stats on the reports dashboard."""
    # Calculate total signoffs
    total_signoffs = Signoff.objects.count()
    
    # Calculate overall completion rate
    students = Student.objects.filter(active=True)
    total_required_parts = Part.objects.filter(is_required=True).count()
    
    if students.count() > 0 and total_required_parts > 0:
        # Get total approved signoffs for required parts
        total_approved = Signoff.objects.filter(
            status='approved',
            part__is_required=True
        ).count()
        
        # Calculate theoretical maximum (all students complete all required parts)
        theoretical_max = students.count() * total_required_parts
        
        # Calculate average completion percentage
        avg_completion = (total_approved / theoretical_max) * 100
    else:
        avg_completion = 0
    
    return JsonResponse({
        'total_signoffs': total_signoffs,
        'avg_completion': round(avg_completion, 1)
    })

# Helper for CSS classes
def get_status_css_class(status):
    """Get CSS class for signoff status."""
    status_classes = {
        'approved': 'bg-success text-white',
        'rejected': 'bg-danger text-white',
        'pending': 'bg-warning',
        'not_started': 'bg-light text-muted',
    }
    return status_classes.get(status, 'bg-light')

def get_completion_css_class(percentage):
    """Get CSS class based on completion percentage."""
    if percentage >= 100:
        return 'bg-success text-white'
    elif percentage >= 75:
        return 'bg-info text-white'
    elif percentage >= 50:
        return 'bg-primary text-white'
    elif percentage > 0:
        return 'bg-warning'
    else:
        return 'bg-light text-muted'