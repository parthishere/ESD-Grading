from django.db import models
from django.contrib.auth.models import User, Group, Permission
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.contenttypes.models import ContentType

class UserRole(models.Model):
    """Model representing user roles in the system."""
    ROLE_CHOICES = (
        ('instructor', 'Instructor'),
        ('ta', 'Teaching Assistant'),
        ('student', 'Student'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='role')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='ta')
    
    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"
    
    def save(self, *args, **kwargs):
        """Override save to ensure permissions are set correctly."""
        is_new = self.pk is None
        super(UserRole, self).save(*args, **kwargs)
        
        # Set permissions based on role
        if is_new or True:  # Always update permissions
            # Clear existing groups
            self.user.groups.clear()
            
            # Add to appropriate group based on role
            group, created = Group.objects.get_or_create(name=self.role)
            self.user.groups.add(group)
            
            # Update user permissions based on role
            if self.role == 'instructor':
                # Instructors can do everything
                self.user.is_staff = True
            elif self.role == 'ta':
                # TAs can't manage users or upload student lists
                self.user.is_staff = False
            else:
                # Students have minimal permissions
                self.user.is_staff = False
            
            self.user.save()


class Lab(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateTimeField()   
    total_points = models.DecimalField(max_digits=5, decimal_places=2)
    
    def __str__(self):
        return f"ECEN5613 - {self.name}"
        
    def get_student_score(self, student):
        """Get a student's total score for this lab."""
        total_score = 0
        
        # Get all parts for this lab
        parts = self.parts.all()
        
        # For each part, get the student's score
        for part in parts:
            # Get the max contribution this part can make to the lab grade
            part_contribution = part.get_contribution_to_lab()
            
            # Get the student's percentage score for this part
            part_percentage = part.get_student_percentage(student) / 100
            
            # Add the weighted score to the total
            total_score += part_contribution * part_percentage
            
        return total_score
        
    def get_student_percentage(self, student):
        """Get a student's percentage score for this lab."""
        if float(self.total_points) == 0:
            return 0
            
        score = self.get_student_score(student)
        return (score / float(self.total_points)) * 100
        
    def get_grade_letter(self, student):
        """Convert percentage to letter grade."""
        percentage = self.get_student_percentage(student)
        
        if percentage >= 90:
            return 'A'
        elif percentage >= 80:
            return 'B'
        elif percentage >= 70:
            return 'C'
        elif percentage >= 60:
            return 'D'
        else:
            return 'F'

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
        
    def get_max_score(self):
        """Get the maximum possible score for this part."""
        # Sum up weights of all quality criteria
        criteria = self.quality_criteria.all()
        if not criteria:
            return 0
        
        return sum(c.max_points for c in criteria)
        
    def get_student_score(self, student):
        """Get a student's score for this part."""
        # First check if there's a signoff
        try:
            signoff = Signoff.objects.get(student=student, part=self, status='approved')
            return signoff.get_total_quality_score()
        except Signoff.DoesNotExist:
            return 0
            
    def get_student_percentage(self, student):
        """Get a student's score as a percentage of max possible."""
        max_score = self.get_max_score()
        if max_score == 0:
            return 0
            
        return (self.get_student_score(student) / max_score) * 100
        
    def get_contribution_to_lab(self):
        """Calculate how many points this part contributes to the overall lab grade."""
        # Get count of parts in this lab
        parts_count = Part.objects.filter(lab=self.lab).count()
        if parts_count == 0:
            return 0
            
        # Each part is worth an equal fraction of the lab's total points
        return self.lab.total_points / parts_count
    
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
        
    def get_contribution_to_part(self, lab_total_points):
        """Calculate how many points this criteria contributes to the overall lab grade."""
        # Get the total weight of all criteria for this part
        total_weight = sum(c.weight for c in QualityCriteria.objects.filter(part=self.part))
        if total_weight == 0:
            return 0
            
        # Calculate what fraction of the part's grade this criteria represents
        part_fraction = self.weight / total_weight
            
        # Calculate part's contribution to lab total
        part_points = lab_total_points / Part.objects.filter(lab=self.part.lab).count()
            
        # Return this criteria's contribution
        return part_fraction * part_points

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
        
    def get_overall_grade(self):
        """Calculate student's overall grade across all labs."""
        labs = Lab.objects.all()
        if not labs:
            return 0
            
        total_points = 0
        earned_points = 0
        
        for lab in labs:
            total_points += float(lab.total_points)
            earned_points += lab.get_student_score(self)
            
        if total_points == 0:
            return 0
            
        return (earned_points / total_points) * 100
        
    def get_course_letter_grade(self):
        """Get student's overall letter grade."""
        percentage = self.get_overall_grade()
        
        if percentage >= 90:
            return 'A'
        elif percentage >= 80:
            return 'B'
        elif percentage >= 70:
            return 'C'
        elif percentage >= 60:
            return 'D'
        else:
            return 'F'

class Signoff(models.Model):
    """Model representing a signoff for a student on a lab part."""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='signoffs')
    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name='signoffs')
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='taken_signoffs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    comments = models.TextField(blank=True)
    date_submitted = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('student', 'part')
        ordering = ['-date_updated']
    
    def __str__(self):
        return f"{self.student} - {self.part} - {self.status}"
    
    def get_total_quality_score(self):
        """Get the total score based on quality criteria."""
        scores = self.quality_scores.all()
        if not scores:
            return 0
        
        # Sum up all quality scores
        return sum(score.score for score in scores)
    
    def get_max_quality_score(self):
        """Get the maximum possible score based on quality criteria."""
        criteria = QualityCriteria.objects.filter(part=self.part)
        if not criteria:
            return 0
        
        # Sum up maximum points for all criteria
        return sum(c.max_points for c in criteria)
    
    def get_quality_percentage(self):
        """Get the quality score as a percentage."""
        max_score = self.get_max_quality_score()
        if max_score == 0:
            return 0
        
        return (self.get_total_quality_score() / max_score) * 100
    
    def get_overall_score(self):
        """Calculate the overall score based on quality scores."""
        scores = self.quality_scores.all()
        if not scores:
            # Default to "Meets Requirements" (2) if no scores
            return 2
            
        total_score = sum(score.score for score in scores)
        total_max = sum(score.criteria.max_points for score in scores)
        
        if total_max == 0:
            return 2
            
        ratio = total_score / total_max
        
        # Map ratio to a 0-4 scale
        if ratio == 0:
            return 0  # Not Applicable
        elif ratio <= 0.25:
            return 1  # Poor/Not Complete
        elif ratio <= 0.5:
            return 2  # Meets Requirements
        elif ratio <= 0.75:
            return 3  # Exceeds Requirements
        else:
            return 4  # Outstanding
    
class QualityScore(models.Model):
    """Model representing a score for a specific quality criteria on a signoff."""
    signoff = models.ForeignKey(Signoff, on_delete=models.CASCADE, related_name='quality_scores')
    criteria = models.ForeignKey(QualityCriteria, on_delete=models.CASCADE, related_name='scores')
    score = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    
    class Meta:
        unique_together = ('signoff', 'criteria')
    
    def __str__(self):
        return f"{self.signoff} - {self.criteria} - {self.score}"
    
    @property
    def weighted_score(self):
        """Calculate the weighted score."""
        if self.criteria.max_points == 0:
            return 0
        return (self.score / self.criteria.max_points) * self.criteria.weight
        
    @property
    def percentage(self):
        """Calculate score as a percentage of max points."""
        if self.criteria.max_points == 0:
            return 0
        return (self.score / self.criteria.max_points) * 100
    
