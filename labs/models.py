from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class Lab(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateTimeField()   
    total_points = models.DecimalField(max_digits=5, decimal_places=2)
    
    def __str__(self):
        return f"ECEN5613 - {self.name}"

class Part(models.Model):
    """Model representing a part of a lab."""
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='parts')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['lab', 'order']
        
    def __str__(self):
        return f"{self.lab.name} - {self.name}" 
    
class QualityCriteria(models.Model):
    """Model representing grading criteria for a part."""
    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name='quality_criteria')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    max_points = models.PositiveIntegerField(default=10)
    weight = models.FloatField(default=1.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    
    class Meta:
        verbose_name_plural = "Quality Criteria"
        ordering = ['part', 'name']
        
    def __str__(self):
        return f"{self.part} - {self.name}"

class Student(models.Model):
    """Model representing a student."""
    student_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    batch = models.DateField(auto_now=False, auto_now_add=False)
    active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} ({self.student_id})"
    
    @property
    def get_completion_status(self):
        """Get the student's overall completion status across all labs."""
        total_parts = Part.objects.filter(is_required=True).count()
        completed_parts = Signoff.objects.filter(
            student=self, 
            status='approved',
            part__is_required=True
        ).values('part').distinct().count()
        
        if total_parts == 0:
            return 0
        
        return (completed_parts / total_parts) * 100

class Signoff(models.Model):
    """Model representing a signoff for a student on a lab part."""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='signoffs')
    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name='signoffs')
    TA = models.ForeignKey(User, on_delete=models.CASCADE, related_name='taken_signoffs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    comments = models.TextField(blank=True)
    date_submitted = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('student', 'part')
        ordering = ['-date_updated']
    
    def __str__(self):
        return f"{self.student} - {self.part} - {self.status}"
    
    
