from django import forms
from django.contrib.auth.models import User
from .models import Student, Lab, Part, QualityCriteria, Signoff, UserRole

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