from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseRedirect
from .models import *
from .forms import StudentUploadForm, UserRoleForm
from django.shortcuts import render, redirect, reverse
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test, login_required
from django.db.models import Count, Avg, Sum, F, Q, Case, When, Value, IntegerField
import datetime
from decimal import Decimal
import pandas as pd
from io import BytesIO
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
                    quality_points = 0
                    quality_max_points = 0
                    
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
                            
                            quality_points += weighted_score
                            quality_max_points += max_weighted
                        except QualityScore.DoesNotExist:
                            quality_scores.append({
                                'criteria': criteria,
                                'score': None,
                                'weighted_score': 0,
                                'max_weighted': float(criteria.weight) * float(lab.total_points)
                            })
                            quality_max_points += float(criteria.weight) * float(lab.total_points)
                    
                    # Get evaluation sheet data if it exists
                    evaluation_sheet_data = None
                    eval_points = 0
                    eval_max_points = 0
                    
                    try:
                        eval_sheet = EvaluationSheet.objects.get(signoff=signoff)
                        
                        # Calculate earned marks for each criterion
                        cleanliness_earned = float(eval_sheet.cleanliness_max_marks) * float(EvaluationSheet.STATUS_TO_SCORE.get(eval_sheet.cleanliness, 0))
                        hardware_earned = float(eval_sheet.hardware_max_marks) * float(EvaluationSheet.STATUS_TO_SCORE.get(eval_sheet.hardware, 0))
                        timeliness_earned = float(eval_sheet.timeliness_max_marks) * float(EvaluationSheet.STATUS_TO_SCORE.get(eval_sheet.timeliness, 0))
                        student_preparation_earned = float(eval_sheet.student_preparation_max_marks) * float(EvaluationSheet.STATUS_TO_SCORE.get(eval_sheet.student_preparation, 0))
                        code_implementation_earned = float(eval_sheet.code_implementation_max_marks) * float(EvaluationSheet.STATUS_TO_SCORE.get(eval_sheet.code_implementation, 0))
                        commenting_earned = float(eval_sheet.commenting_max_marks) * float(EvaluationSheet.STATUS_TO_SCORE.get(eval_sheet.commenting, 0))
                        schematic_earned = float(eval_sheet.schematic_max_marks) * float(EvaluationSheet.STATUS_TO_SCORE.get(eval_sheet.schematic, 0))
                        course_participation_earned = float(eval_sheet.course_participation_max_marks) * float(EvaluationSheet.STATUS_TO_SCORE.get(eval_sheet.course_participation, 0))
                        
                        # Get status display values
                        status_dict = dict(EvaluationSheet.STATUS_CHOICES)
                        
                        evaluation_sheet_data = {
                            'cleanliness': eval_sheet.cleanliness,
                            'cleanliness_display': status_dict.get(eval_sheet.cleanliness, 'Unknown'),
                            'cleanliness_max_marks': float(eval_sheet.cleanliness_max_marks),
                            'cleanliness_earned': cleanliness_earned,
                            
                            'hardware': eval_sheet.hardware,
                            'hardware_display': status_dict.get(eval_sheet.hardware, 'Unknown'),
                            'hardware_max_marks': float(eval_sheet.hardware_max_marks),
                            'hardware_earned': hardware_earned,
                            
                            'timeliness': eval_sheet.timeliness,
                            'timeliness_display': status_dict.get(eval_sheet.timeliness, 'Unknown'),
                            'timeliness_max_marks': float(eval_sheet.timeliness_max_marks),
                            'timeliness_earned': timeliness_earned,
                            
                            'student_preparation': eval_sheet.student_preparation,
                            'student_preparation_display': status_dict.get(eval_sheet.student_preparation, 'Unknown'),
                            'student_preparation_max_marks': float(eval_sheet.student_preparation_max_marks),
                            'student_preparation_earned': student_preparation_earned,
                            
                            'code_implementation': eval_sheet.code_implementation,
                            'code_implementation_display': status_dict.get(eval_sheet.code_implementation, 'Unknown'),
                            'code_implementation_max_marks': float(eval_sheet.code_implementation_max_marks),
                            'code_implementation_earned': code_implementation_earned,
                            
                            'commenting': eval_sheet.commenting,
                            'commenting_display': status_dict.get(eval_sheet.commenting, 'Unknown'),
                            'commenting_max_marks': float(eval_sheet.commenting_max_marks),
                            'commenting_earned': commenting_earned,
                            
                            'schematic': eval_sheet.schematic,
                            'schematic_display': status_dict.get(eval_sheet.schematic, 'Unknown'),
                            'schematic_max_marks': float(eval_sheet.schematic_max_marks),
                            'schematic_earned': schematic_earned,
                            
                            'course_participation': eval_sheet.course_participation,
                            'course_participation_display': status_dict.get(eval_sheet.course_participation, 'Unknown'),
                            'course_participation_max_marks': float(eval_sheet.course_participation_max_marks),
                            'course_participation_earned': course_participation_earned,
                            
                            'total_earned_marks': float(eval_sheet.get_earned_marks()),
                            'total_max_marks': float(eval_sheet.get_total_max_marks())
                        }
                        
                        eval_points = evaluation_sheet_data['total_earned_marks']
                        eval_max_points = evaluation_sheet_data['total_max_marks']
                        
                    except EvaluationSheet.DoesNotExist:
                        pass
                    
                    # Calculate total part points including both quality criteria and evaluation sheet
                    part_points = quality_points + eval_points
                    max_part_points = quality_max_points + eval_max_points
                    
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
                    'quality_earned_points': quality_points if status == 'approved' else 0,
                    'quality_max_points': quality_max_points,
                    'evaluation_sheet': evaluation_sheet_data,
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
                    
                    # Add evaluation sheet data if available
                    if part_data['evaluation_sheet']:
                        eval_sheet = part_data['evaluation_sheet']
                        writer.writerow(['', '', 'Evaluation Sheet', 'Total Score', f"{eval_sheet['total_earned_marks']:.2f}/{eval_sheet['total_max_marks']:.2f}"])
                        
                        # Add evaluation criteria
                        writer.writerow(['', '', '', 'Cleanliness', eval_sheet['cleanliness_display'], f"{eval_sheet['cleanliness_earned']:.2f}/{eval_sheet['cleanliness_max_marks']:.2f}"])
                        writer.writerow(['', '', '', 'Hardware', eval_sheet['hardware_display'], f"{eval_sheet['hardware_earned']:.2f}/{eval_sheet['hardware_max_marks']:.2f}"])
                        writer.writerow(['', '', '', 'Timeliness', eval_sheet['timeliness_display'], f"{eval_sheet['timeliness_earned']:.2f}/{eval_sheet['timeliness_max_marks']:.2f}"])
                        writer.writerow(['', '', '', 'Student Preparation', eval_sheet['student_preparation_display'], f"{eval_sheet['student_preparation_earned']:.2f}/{eval_sheet['student_preparation_max_marks']:.2f}"])
                        writer.writerow(['', '', '', 'Code Implementation', eval_sheet['code_implementation_display'], f"{eval_sheet['code_implementation_earned']:.2f}/{eval_sheet['code_implementation_max_marks']:.2f}"])
                        writer.writerow(['', '', '', 'Commenting', eval_sheet['commenting_display'], f"{eval_sheet['commenting_earned']:.2f}/{eval_sheet['commenting_max_marks']:.2f}"])
                        writer.writerow(['', '', '', 'Schematic', eval_sheet['schematic_display'], f"{eval_sheet['schematic_earned']:.2f}/{eval_sheet['schematic_max_marks']:.2f}"])
                        writer.writerow(['', '', '', 'Course Participation', eval_sheet['course_participation_display'], f"{eval_sheet['course_participation_earned']:.2f}/{eval_sheet['course_participation_max_marks']:.2f}"])
            
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
    print("heya")
    print(student_id)
    print(lab_id)
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
        
        # Get quality scores for this signoff
        quality_scores = QualityScore.objects.filter(
            signoff=signoff
        ).values(
            'criteria_id', 'score', 'criteria__max_points', 'criteria__name'
        )
            
        # Prepare response
        response = {
            'found': True,
            'id': signoff.id,
            'status': signoff.status,
            'comments': signoff.comments,
            'date_updated': signoff.date_updated.isoformat(),
            'overall_score': 2,  # Default to "Meets Requirements"
            'quality_scores': list(quality_scores),
            'history': list(history),
            'has_evaluation_sheet': False,
            'evaluation_sheet': {}
        }
        
        # Get evaluation sheet if it exists
        try:
            evaluation_sheet = EvaluationSheet.objects.get(signoff=signoff)
            
            # Add evaluation sheet data to response
            response['has_evaluation_sheet'] = True
            response['evaluation_sheet'] = {
                'cleanliness': {
                    'value': evaluation_sheet.cleanliness,
                    'max_marks': float(evaluation_sheet.cleanliness_max_marks)
                },
                'hardware': {
                    'value': evaluation_sheet.hardware,
                    'max_marks': float(evaluation_sheet.hardware_max_marks)
                },
                'timeliness': {
                    'value': evaluation_sheet.timeliness,
                    'max_marks': float(evaluation_sheet.timeliness_max_marks)
                },
                'student_preparation': {
                    'value': evaluation_sheet.student_preparation,
                    'max_marks': float(evaluation_sheet.student_preparation_max_marks)
                },
                'code_implementation': {
                    'value': evaluation_sheet.code_implementation,
                    'max_marks': float(evaluation_sheet.code_implementation_max_marks)
                },
                'commenting': {
                    'value': evaluation_sheet.commenting,
                    'max_marks': float(evaluation_sheet.commenting_max_marks)
                },
                'schematic': {
                    'value': evaluation_sheet.schematic,
                    'max_marks': float(evaluation_sheet.schematic_max_marks)
                },
                'course_participation': {
                    'value': evaluation_sheet.course_participation,
                    'max_marks': float(evaluation_sheet.course_participation_max_marks)
                },
                'total_marks': float(evaluation_sheet.get_earned_marks()),
                'total_max_marks': float(evaluation_sheet.get_total_max_marks()),
                'percentage': float(evaluation_sheet.get_percentage())
            }
        except EvaluationSheet.DoesNotExist:
            pass
        
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
    
    # Process evaluation sheet if present
    if any(key.startswith('eval_') for key in request.POST.keys()):
        # Get or create the evaluation sheet for this signoff
        try:
            evaluation_sheet = EvaluationSheet.objects.get(signoff=signoff)
        except EvaluationSheet.DoesNotExist:
            evaluation_sheet = EvaluationSheet(signoff=signoff)
        
        # Extract evaluation fields from the form
        if 'eval_cleanliness' in request.POST:
            evaluation_sheet.cleanliness = request.POST.get('eval_cleanliness')
        if 'eval_hardware' in request.POST:
            evaluation_sheet.hardware = request.POST.get('eval_hardware')
        if 'eval_timeliness' in request.POST:
            evaluation_sheet.timeliness = request.POST.get('eval_timeliness')
        if 'eval_student_preparation' in request.POST:
            evaluation_sheet.student_preparation = request.POST.get('eval_student_preparation')
        if 'eval_code_implementation' in request.POST:
            evaluation_sheet.code_implementation = request.POST.get('eval_code_implementation')
        if 'eval_commenting' in request.POST:
            evaluation_sheet.commenting = request.POST.get('eval_commenting')
        if 'eval_schematic' in request.POST:
            evaluation_sheet.schematic = request.POST.get('eval_schematic')
        if 'eval_course_participation' in request.POST:
            evaluation_sheet.course_participation = request.POST.get('eval_course_participation')
            
        # Save custom max marks if provided
        if 'eval_cleanliness_max' in request.POST and request.POST.get('eval_cleanliness_max'):
            evaluation_sheet.cleanliness_max_marks = Decimal(request.POST.get('eval_cleanliness_max'))
        if 'eval_hardware_max' in request.POST and request.POST.get('eval_hardware_max'):
            evaluation_sheet.hardware_max_marks = Decimal(request.POST.get('eval_hardware_max'))
        if 'eval_timeliness_max' in request.POST and request.POST.get('eval_timeliness_max'):
            evaluation_sheet.timeliness_max_marks = Decimal(request.POST.get('eval_timeliness_max'))
        if 'eval_student_preparation_max' in request.POST and request.POST.get('eval_student_preparation_max'):
            evaluation_sheet.student_preparation_max_marks = Decimal(request.POST.get('eval_student_preparation_max'))
        if 'eval_code_implementation_max' in request.POST and request.POST.get('eval_code_implementation_max'):
            evaluation_sheet.code_implementation_max_marks = Decimal(request.POST.get('eval_code_implementation_max'))
        if 'eval_commenting_max' in request.POST and request.POST.get('eval_commenting_max'):
            evaluation_sheet.commenting_max_marks = Decimal(request.POST.get('eval_commenting_max'))
        if 'eval_schematic_max' in request.POST and request.POST.get('eval_schematic_max'):
            evaluation_sheet.schematic_max_marks = Decimal(request.POST.get('eval_schematic_max'))
        if 'eval_course_participation_max' in request.POST and request.POST.get('eval_course_participation_max'):
            evaluation_sheet.course_participation_max_marks = Decimal(request.POST.get('eval_course_participation_max'))
        
        # Save the evaluation sheet
        evaluation_sheet.save()
    
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
@login_required
def student_detail(request, student_id):
    """Display detailed information about a specific student."""
    student = get_object_or_404(Student, id=student_id)
    
    # Get all labs
    labs = Lab.objects.all().order_by('due_date')
    
    # Get student progress data
    total_parts_count = Part.objects.filter(is_required=True).count()
    completed_parts_count = Signoff.objects.filter(
        student=student, 
        status='approved',
        part__is_required=True
    ).values('part').distinct().count()
    
    # Calculate points
    total_points = sum(lab.total_points for lab in labs)
    earned_points = sum(lab.get_student_score(student) for lab in labs)
    
    # Categorize labs by completion status
    completed_labs = []
    in_progress_labs = []
    not_started_labs = []
    
    for lab in labs:
        lab_parts = lab.parts.all()
        approved_parts = Signoff.objects.filter(
            student=student,
            part__in=lab_parts,
            status='approved'
        ).count()
        
        if approved_parts == lab_parts.count() and lab_parts.count() > 0:
            completed_labs.append(lab)
        elif approved_parts > 0:
            in_progress_labs.append(lab)
        else:
            not_started_labs.append(lab)
    
    # Get recent signoffs
    recent_signoffs = Signoff.objects.filter(
        student=student
    ).select_related('part', 'part__lab').order_by('-date_updated')[:5]
    
    context = {
        'student': student,
        'labs': labs,
        'completed_labs': completed_labs,
        'in_progress_labs': in_progress_labs,
        'not_started_labs': not_started_labs,
        'total_parts_count': total_parts_count,
        'completed_parts_count': completed_parts_count,
        'total_points': total_points,
        'earned_points': earned_points,
        'recent_signoffs': recent_signoffs
    }
    
    return render(request, 'labs/student_detail.html', context)

@login_required
def lab_detail(request, lab_id):
    """Display detailed information about a specific lab."""
    lab = get_object_or_404(Lab, id=lab_id)
    
    # Check if we're filtering by student
    student_id = request.GET.get('student_id')
    filtered_student = None
    if student_id:
        filtered_student = get_object_or_404(Student, id=student_id)
    
    # Get all parts for this lab
    parts = lab.parts.all().order_by('order')
    
    # Get all active students
    students = Student.objects.filter(active=True)
    total_students = students.count()
    
    # Calculate lab completion stats
    approved_signoffs = Signoff.objects.filter(
        part__lab=lab,
        status='approved'
    ).count()
    
    total_required_signoffs = students.count() * parts.filter(is_required=True).count()
    completion_percentage = (approved_signoffs / total_required_signoffs * 100) if total_required_signoffs > 0 else 0
    
    # Calculate average score
    avg_points = 0
    avg_score = 0
    
    if total_students > 0:
        total_lab_score = sum(lab.get_student_score(student) for student in students)
        avg_points = total_lab_score / total_students
        avg_score = (avg_points / lab.total_points * 100) if lab.total_points > 0 else 0
    
    # Calculate student completion status
    completed_students = 0
    in_progress_students = 0
    not_started_students = 0
    
    # Grade distribution
    a_grade_count = 0
    b_grade_count = 0
    c_grade_count = 0
    d_grade_count = 0
    f_grade_count = 0
    
    # Build student progress data
    student_progress = []
    
    for student in students:
        if filtered_student and student.id != filtered_student.id:
            continue
            
        # Get all signoffs for this student and lab
        student_signoffs = Signoff.objects.filter(
            student=student,
            part__lab=lab
        ).select_related('part')
        
        # Calculate completion status
        approved_parts_count = student_signoffs.filter(status='approved').count()
        total_parts_count = parts.count()
        
        status = 'not_started'
        if approved_parts_count == total_parts_count and total_parts_count > 0:
            status = 'completed'
            completed_students += 1
        elif approved_parts_count > 0:
            status = 'in_progress'
            in_progress_students += 1
        else:
            not_started_students += 1
        
        # Calculate percentage and grade
        percentage = lab.get_student_percentage(student)
        
        # Update grade distribution
        if percentage >= 90:
            a_grade_count += 1
        elif percentage >= 80:
            b_grade_count += 1
        elif percentage >= 70:
            c_grade_count += 1
        elif percentage >= 60:
            d_grade_count += 1
        else:
            f_grade_count += 1
        
        # Get last activity date
        last_activity = student_signoffs.order_by('-date_updated').first()
        
        student_progress.append({
            'student': student,
            'status': status,
            'percentage': percentage,
            'last_activity': last_activity.date_updated if last_activity else None,
            'approved_parts': approved_parts_count,
            'total_parts': total_parts_count
        })
    
    # Add part stats
    for part in parts:
        part_approved_count = Signoff.objects.filter(
            part=part,
            status='approved'
        ).count()
        
        part.approved_count = part_approved_count
        part.completion_percentage = (part_approved_count / total_students * 100) if total_students > 0 else 0
    
    context = {
        'lab': lab,
        'filtered_student': filtered_student,
        'student_progress': student_progress,
        'total_students': total_students,
        'approved_signoffs': approved_signoffs,
        'total_required_signoffs': total_required_signoffs,
        'completion_percentage': completion_percentage,
        'avg_points': avg_points,
        'avg_score': avg_score,
        'completed_students': completed_students,
        'in_progress_students': in_progress_students,
        'not_started_students': not_started_students,
        'a_grade_count': a_grade_count,
        'b_grade_count': b_grade_count,
        'c_grade_count': c_grade_count,
        'd_grade_count': d_grade_count,
        'f_grade_count': f_grade_count
    }
    
    return render(request, 'labs/lab_detail.html', context)

@login_required
def part_detail(request, part_id):
    """Display detailed information about a specific lab part."""
    part = get_object_or_404(Part, id=part_id)
    
    # Check if we're filtering by student
    student_id = request.GET.get('student_id')
    filtered_student = None
    if student_id:
        filtered_student = get_object_or_404(Student, id=student_id)
    
    # Get all active students
    students = Student.objects.filter(active=True)
    total_students = students.count()
    
    # Get all signoffs for this part
    signoffs = Signoff.objects.filter(part=part).select_related('student', 'instructor')
    
    # Calculate signoff stats
    approved_signoffs = signoffs.filter(status='approved').count()
    rejected_signoffs = signoffs.filter(status='rejected').count()
    pending_signoffs = signoffs.filter(status='pending').count()
    
    # Calculate completion percentage
    completion_percentage = (approved_signoffs / total_students * 100) if total_students > 0 else 0
    
    # Calculate average score
    avg_points = 0
    avg_score = 0
    max_points = part.get_max_score()
    
    if approved_signoffs > 0:
        total_score = sum(signoff.get_total_quality_score() for signoff in signoffs.filter(status='approved'))
        avg_points = total_score / approved_signoffs
        avg_score = (avg_points / max_points * 100) if max_points > 0 else 0
    
    # Get quality criteria with average scores
    quality_criteria = QualityCriteria.objects.filter(part=part)
    
    for criteria in quality_criteria:
        # Calculate average score for this criteria
        criteria_scores = QualityScore.objects.filter(
            criteria=criteria,
            signoff__status='approved'
        )
        
        if criteria_scores:
            criteria.avg_score = sum(score.score for score in criteria_scores) / criteria_scores.count()
            criteria.avg_percentage = (criteria.avg_score / criteria.max_points * 100) if criteria.max_points > 0 else 0
        else:
            criteria.avg_score = None
            criteria.avg_percentage = None
    
    # Get recent signoffs
    recent_signoffs = signoffs.order_by('-date_updated')[:5]
    
    # Get students who haven't started this part
    signoff_student_ids = signoffs.values_list('student__id', flat=True)
    not_started_students = students.exclude(id__in=signoff_student_ids)
    
    # Filter signoffs by status for tabs
    approved_signoff_list = signoffs.filter(status='approved').order_by('-date_updated')
    rejected_signoff_list = signoffs.filter(status='rejected').order_by('-date_updated')
    pending_signoff_list = signoffs.filter(status='pending').order_by('-date_updated')
    
    # Filter by student if specified
    if filtered_student:
        approved_signoff_list = approved_signoff_list.filter(student=filtered_student)
        rejected_signoff_list = rejected_signoff_list.filter(student=filtered_student)
        pending_signoff_list = pending_signoff_list.filter(student=filtered_student)
        not_started_students = not_started_students.filter(id=filtered_student.id)
    
    context = {
        'part': part,
        'filtered_student': filtered_student,
        'total_students': total_students,
        'approved_signoffs': approved_signoffs,
        'rejected_signoffs': rejected_signoffs,
        'pending_signoffs': pending_signoffs,
        'not_started': total_students - approved_signoffs - rejected_signoffs - pending_signoffs,
        'completion_percentage': completion_percentage,
        'avg_points': avg_points,
        'avg_score': avg_score,
        'max_points': max_points,
        'quality_criteria': quality_criteria,
        'recent_signoffs': recent_signoffs,
        'not_started_students': not_started_students,
        'all_signoffs': signoffs.order_by('-date_updated'),
        'approved_signoff_list': approved_signoff_list,
        'rejected_signoff_list': rejected_signoff_list,
        'pending_signoff_list': pending_signoff_list
    }
    
    return render(request, 'labs/part_detail.html', context)

@login_required
def signoff_list(request):
    """Display a list of all signoffs."""
    # Get filter parameters
    status = request.GET.get('status')
    lab_id = request.GET.get('lab_id')
    student_id = request.GET.get('student_id')
    
    # Start with all signoffs
    signoffs = Signoff.objects.all().select_related(
        'student', 'part', 'part__lab', 'instructor'
    ).order_by('-date_updated')
    
    # Apply filters
    if status:
        signoffs = signoffs.filter(status=status)
    
    if lab_id:
        signoffs = signoffs.filter(part__lab_id=lab_id)
    
    if student_id:
        signoffs = signoffs.filter(student_id=student_id)
    
    # Get filter options for dropdowns
    labs = Lab.objects.all().order_by('name')
    students = Student.objects.filter(active=True).order_by('name')
    
    context = {
        'signoffs': signoffs,
        'labs': labs,
        'students': students,
        'status_filter': status,
        'lab_filter': lab_id,
        'student_filter': student_id
    }
    
    return render(request, 'labs/signoff_list.html', context)

@login_required
def signoff_detail(request, signoff_id):
    """Display detailed information about a specific signoff."""
    signoff = get_object_or_404(Signoff, id=signoff_id)
    
    # Get quality scores
    quality_scores = QualityScore.objects.filter(signoff=signoff).select_related('criteria')
    quality_total = signoff.get_total_quality_score()
    quality_max = signoff.get_max_quality_score()
    
    # Get evaluation sheet if it exists
    try:
        evaluation_sheet = EvaluationSheet.objects.get(signoff=signoff)
        
        # Calculate earned marks for displaying
        cleanliness_earned = float(evaluation_sheet.cleanliness_max_marks) * float(EvaluationSheet.STATUS_TO_SCORE.get(evaluation_sheet.cleanliness, 0))
        hardware_earned = float(evaluation_sheet.hardware_max_marks) * float(EvaluationSheet.STATUS_TO_SCORE.get(evaluation_sheet.hardware, 0))
        timeliness_earned = float(evaluation_sheet.timeliness_max_marks) * float(EvaluationSheet.STATUS_TO_SCORE.get(evaluation_sheet.timeliness, 0))
        student_preparation_earned = float(evaluation_sheet.student_preparation_max_marks) * float(EvaluationSheet.STATUS_TO_SCORE.get(evaluation_sheet.student_preparation, 0))
        code_implementation_earned = float(evaluation_sheet.code_implementation_max_marks) * float(EvaluationSheet.STATUS_TO_SCORE.get(evaluation_sheet.code_implementation, 0))
        commenting_earned = float(evaluation_sheet.commenting_max_marks) * float(EvaluationSheet.STATUS_TO_SCORE.get(evaluation_sheet.commenting, 0))
        schematic_earned = float(evaluation_sheet.schematic_max_marks) * float(EvaluationSheet.STATUS_TO_SCORE.get(evaluation_sheet.schematic, 0))
        course_participation_earned = float(evaluation_sheet.course_participation_max_marks) * float(EvaluationSheet.STATUS_TO_SCORE.get(evaluation_sheet.course_participation, 0))
    except EvaluationSheet.DoesNotExist:
        evaluation_sheet = None
        cleanliness_earned = hardware_earned = timeliness_earned = student_preparation_earned = 0
        code_implementation_earned = commenting_earned = schematic_earned = course_participation_earned = 0
    
    # Get signoff history
    signoff_history = Signoff.objects.filter(
        student=signoff.student,
        part=signoff.part
    ).order_by('-date_updated').values(
        'status', 'comments', 'date_updated', 'instructor__username'
    )
    
    context = {
        'signoff': signoff,
        'quality_scores': quality_scores,
        'quality_total': quality_total,
        'quality_max': quality_max,
        'evaluation_sheet': evaluation_sheet,
        'cleanliness_earned': cleanliness_earned,
        'hardware_earned': hardware_earned,
        'timeliness_earned': timeliness_earned,
        'student_preparation_earned': student_preparation_earned,
        'code_implementation_earned': code_implementation_earned,
        'commenting_earned': commenting_earned,
        'schematic_earned': schematic_earned,
        'course_participation_earned': course_participation_earned,
        'signoff_history': signoff_history
    }
    
    return render(request, 'labs/signoff_detail.html', context)

@login_required
def signoff_edit(request, signoff_id):
    """Edit a specific signoff."""
    signoff = get_object_or_404(Signoff, id=signoff_id)
    
    if request.method == 'POST':
        # Update signoff basic info
        signoff.status = request.POST.get('status')
        signoff.comments = request.POST.get('comments')
        signoff.instructor = request.user
        signoff.save()
        
        # Update quality scores
        for key, value in request.POST.items():
            if key.startswith('criteria_'):
                criteria_id = key.split('_')[1]
                try:
                    criteria = QualityCriteria.objects.get(id=criteria_id)
                    
                    # Convert radio value to points based on criteria's max_points
                    value_map = {
                        '0': 0,  # Not Applicable
                        '1': int(criteria.max_points * 0.25),  # Poor/Not Complete - 25%
                        '2': int(criteria.max_points * 0.5),  # Meets Requirements - 50%
                        '3': int(criteria.max_points * 0.75),  # Exceeds Requirements - 75%
                        '4': criteria.max_points  # Outstanding - 100%
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
        
        # Process evaluation sheet
        if any(key.startswith('eval_') for key in request.POST.keys()):
            # Get or create the evaluation sheet
            try:
                evaluation_sheet = EvaluationSheet.objects.get(signoff=signoff)
            except EvaluationSheet.DoesNotExist:
                evaluation_sheet = EvaluationSheet(signoff=signoff)
            
            # Update evaluation fields
            if 'eval_cleanliness' in request.POST:
                evaluation_sheet.cleanliness = request.POST.get('eval_cleanliness')
            if 'eval_hardware' in request.POST:
                evaluation_sheet.hardware = request.POST.get('eval_hardware')
            if 'eval_timeliness' in request.POST:
                evaluation_sheet.timeliness = request.POST.get('eval_timeliness')
            if 'eval_student_preparation' in request.POST:
                evaluation_sheet.student_preparation = request.POST.get('eval_student_preparation')
            if 'eval_code_implementation' in request.POST:
                evaluation_sheet.code_implementation = request.POST.get('eval_code_implementation')
            if 'eval_commenting' in request.POST:
                evaluation_sheet.commenting = request.POST.get('eval_commenting')
            if 'eval_schematic' in request.POST:
                evaluation_sheet.schematic = request.POST.get('eval_schematic')
            if 'eval_course_participation' in request.POST:
                evaluation_sheet.course_participation = request.POST.get('eval_course_participation')
            
            # Update max marks
            if 'eval_cleanliness_max' in request.POST and request.POST.get('eval_cleanliness_max'):
                evaluation_sheet.cleanliness_max_marks = Decimal(request.POST.get('eval_cleanliness_max'))
            if 'eval_hardware_max' in request.POST and request.POST.get('eval_hardware_max'):
                evaluation_sheet.hardware_max_marks = Decimal(request.POST.get('eval_hardware_max'))
            if 'eval_timeliness_max' in request.POST and request.POST.get('eval_timeliness_max'):
                evaluation_sheet.timeliness_max_marks = Decimal(request.POST.get('eval_timeliness_max'))
            if 'eval_student_preparation_max' in request.POST and request.POST.get('eval_student_preparation_max'):
                evaluation_sheet.student_preparation_max_marks = Decimal(request.POST.get('eval_student_preparation_max'))
            if 'eval_code_implementation_max' in request.POST and request.POST.get('eval_code_implementation_max'):
                evaluation_sheet.code_implementation_max_marks = Decimal(request.POST.get('eval_code_implementation_max'))
            if 'eval_commenting_max' in request.POST and request.POST.get('eval_commenting_max'):
                evaluation_sheet.commenting_max_marks = Decimal(request.POST.get('eval_commenting_max'))
            if 'eval_schematic_max' in request.POST and request.POST.get('eval_schematic_max'):
                evaluation_sheet.schematic_max_marks = Decimal(request.POST.get('eval_schematic_max'))
            if 'eval_course_participation_max' in request.POST and request.POST.get('eval_course_participation_max'):
                evaluation_sheet.course_participation_max_marks = Decimal(request.POST.get('eval_course_participation_max'))
            
            # Save the evaluation sheet
            evaluation_sheet.save()
        
        messages.success(request, "Signoff updated successfully.")
        return redirect('labs:signoff_detail', signoff_id=signoff.id)
    
    # Get quality criteria with current scores
    quality_criteria = QualityCriteria.objects.filter(part=signoff.part)
    
    for criteria in quality_criteria:
        try:
            score = QualityScore.objects.get(signoff=signoff, criteria=criteria)
            if criteria.max_points == 0:
                criteria.score_percentage = 0
            else:
                criteria.score_percentage = (score.score / criteria.max_points) * 100
            
            # Map to radio button values
            if criteria.score_percentage == 0:
                criteria.radio_value = 0  # Not Applicable
            elif criteria.score_percentage <= 25:
                criteria.radio_value = 1  # Poor/Not Complete
            elif criteria.score_percentage <= 50:
                criteria.radio_value = 2  # Meets Requirements
            elif criteria.score_percentage <= 75:
                criteria.radio_value = 3  # Exceeds Requirements
            else:
                criteria.radio_value = 4  # Outstanding
                
            # Set get_score_value for template
            criteria.get_score_value = criteria.score_percentage
        except QualityScore.DoesNotExist:
            criteria.score_percentage = 0
            criteria.radio_value = 2  # Default to Meets Requirements
            criteria.get_score_value = 50  # Default to 50%
    
    # Get evaluation sheet if it exists
    try:
        evaluation_sheet = EvaluationSheet.objects.get(signoff=signoff)
    except EvaluationSheet.DoesNotExist:
        evaluation_sheet = None
    
    context = {
        'signoff': signoff,
        'quality_criteria': quality_criteria,
        'evaluation_sheet': evaluation_sheet
    }
    
    return render(request, 'labs/signoff_edit.html', context)
