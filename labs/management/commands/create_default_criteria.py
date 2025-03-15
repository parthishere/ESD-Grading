from django.core.management.base import BaseCommand
from labs.models import Part

class Command(BaseCommand):
    help = 'Creates default quality criteria for all lab parts that do not have any'

    def handle(self, *args, **options):
        # Get all parts
        parts = Part.objects.all()
        total_parts = parts.count()
        updated_parts = 0
        
        self.stdout.write(f"Found {total_parts} lab parts")
        
        # Check each part
        for part in parts:
            # If part has no quality criteria, create defaults
            if not part.quality_criteria.exists():
                self.stdout.write(f"  Creating default criteria for part: {part}")
                part.create_default_criteria()
                updated_parts += 1
            else:
                self.stdout.write(f"  Part already has criteria: {part}")
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f"Added default criteria to {updated_parts} parts out of {total_parts} total parts"))