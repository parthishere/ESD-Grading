from django import forms
from django.contrib.auth.models import User
from .models import Student, Lab, Part, QualityCriteria, Signoff, UserRole, EvaluationRubric, GradeScale
import json

class StudentUploadForm(forms.Form):
    """Form for uploading a list of students from Excel."""
    excel_file = forms.FileField(
        label='Excel File',
        help_text='Upload an Excel file with student data. Required columns: student_id, name, email, batch (YYYY-MM-DD)'
    )

class UserRoleForm(forms.ModelForm):
    """Form for creating/editing user roles."""
    class Meta:
        model = UserRole
        fields = ['role']
        
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    password1 = forms.CharField(widget=forms.PasswordInput(), required=False, 
                               help_text="Leave blank to keep current password")
    password2 = forms.CharField(widget=forms.PasswordInput(), required=False,
                               label="Confirm Password")
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        if password1 and password1 != password2:
            self.add_error('password2', "Passwords don't match")
            
        return cleaned_data
        
class LabForm(forms.ModelForm):
    """Form for creating and editing labs."""
    class Meta:
        model = Lab
        fields = ['name', 'description', 'due_date', 'total_points', 'grade_scale']
        widgets = {
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'description': forms.Textarea(attrs={'rows': 4}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['grade_scale'].empty_label = "Use Default Grade Scale"
        self.fields['grade_scale'].required = False
        
class PartForm(forms.ModelForm):
    """Form for creating and editing lab parts."""
    class Meta:
        model = Part
        fields = ['lab', 'name', 'description', 'order', 'is_required', 'has_challenges', 'due_date']
        widgets = {
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'description': forms.Textarea(attrs={'rows': 4}),
        }
        
    def __init__(self, *args, lab=None, **kwargs):
        super().__init__(*args, **kwargs)
        if lab:
            self.fields['lab'].initial = lab
            self.fields['lab'].widget = forms.HiddenInput()

class QualityCriteriaForm(forms.ModelForm):
    """Form for creating and editing quality criteria."""
    class Meta:
        model = QualityCriteria
        fields = ['part', 'name', 'description', 'max_points', 'weight']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        
    def __init__(self, *args, part=None, **kwargs):
        super().__init__(*args, **kwargs)
        if part:
            self.fields['part'].initial = part
            self.fields['part'].widget = forms.HiddenInput()
        
class EvaluationRubricForm(forms.ModelForm):
    """Form for creating and editing evaluation rubrics."""
    class Meta:
        model = EvaluationRubric
        fields = ['name', 'description', 'is_default']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }
        
    # Fields for dynamic criteria management
    criteria_json = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 6, 'class': 'criteria-json'}),
        required=False,
        help_text="JSON representation of rubric criteria. Edit with caution."
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Convert criteria_data to JSON string for the form field
        instance = kwargs.get('instance')
        if instance and instance.criteria_data:
            self.fields['criteria_json'].initial = json.dumps(instance.criteria_data, indent=2)
        else:
            # Default rubric structure
            default_criteria = {
                "cleanliness": {"name": "Cleanliness", "max_marks": 5.0},
                "hardware": {"name": "Hardware", "max_marks": 10.0},
                "timeliness": {"name": "Timeliness", "max_marks": 5.0},
                "student_preparation": {"name": "Student Preparation", "max_marks": 10.0},
                "code_implementation": {"name": "Code Implementation", "max_marks": 15.0},
                "commenting": {"name": "Commenting", "max_marks": 5.0},
                "schematic": {"name": "Schematic", "max_marks": 10.0},
                "course_participation": {"name": "Course Participation", "max_marks": 5.0}
            }
            self.fields['criteria_json'].initial = json.dumps(default_criteria, indent=2)
    
    def clean_criteria_json(self):
        criteria_json = self.cleaned_data.get('criteria_json')
        if criteria_json:
            try:
                criteria_data = json.loads(criteria_json)
                
                # Validate criteria structure
                for key, criterion in criteria_data.items():
                    if not isinstance(criterion, dict):
                        raise forms.ValidationError(f"Criterion '{key}' must be a dictionary")
                    if 'name' not in criterion:
                        raise forms.ValidationError(f"Criterion '{key}' must have a 'name' field")
                    if 'max_marks' not in criterion:
                        raise forms.ValidationError(f"Criterion '{key}' must have a 'max_marks' field")
                    
                    # Ensure max_marks is numeric
                    try:
                        float(criterion['max_marks'])
                    except (ValueError, TypeError):
                        raise forms.ValidationError(f"'max_marks' for criterion '{key}' must be a number")
                
                return criteria_data
            except json.JSONDecodeError:
                raise forms.ValidationError("Invalid JSON format")
        return {}
        
class GradeScaleForm(forms.ModelForm):
    """Form for creating and editing grade scales."""
    class Meta:
        model = GradeScale
        fields = [
            'name', 'description', 'is_default',
            'a_plus_threshold', 'a_threshold', 'a_minus_threshold',
            'b_plus_threshold', 'b_threshold', 'b_minus_threshold',
            'c_plus_threshold', 'c_threshold', 'c_minus_threshold',
            'd_plus_threshold', 'd_threshold', 'd_minus_threshold'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        
    def clean(self):
        cleaned_data = super().clean()
        
        # Get all threshold values
        thresholds = [
            ('a_plus_threshold', cleaned_data.get('a_plus_threshold')),
            ('a_threshold', cleaned_data.get('a_threshold')),
            ('a_minus_threshold', cleaned_data.get('a_minus_threshold')),
            ('b_plus_threshold', cleaned_data.get('b_plus_threshold')),
            ('b_threshold', cleaned_data.get('b_threshold')),
            ('b_minus_threshold', cleaned_data.get('b_minus_threshold')),
            ('c_plus_threshold', cleaned_data.get('c_plus_threshold')),
            ('c_threshold', cleaned_data.get('c_threshold')),
            ('c_minus_threshold', cleaned_data.get('c_minus_threshold')),
            ('d_plus_threshold', cleaned_data.get('d_plus_threshold')),
            ('d_threshold', cleaned_data.get('d_threshold')),
            ('d_minus_threshold', cleaned_data.get('d_minus_threshold'))
        ]
        
        # Make sure thresholds are in descending order
        last_value = Decimal('100.0')
        for field_name, value in thresholds:
            if value is None:
                continue
                
            if value > last_value:
                self.add_error(
                    field_name, 
                    f"This threshold ({value}%) must be lower than the previous threshold ({last_value}%)"
                )
            elif value < Decimal('0') or value > Decimal('100'):
                self.add_error(
                    field_name, 
                    f"Threshold must be between 0% and 100%"
                )
            last_value = value
            
        return cleaned_data