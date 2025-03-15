from labs.models import Lab, Part, QualityCriteria

# Get all labs
labs = Lab.objects.all()
print(f"Total labs: {labs.count()}")

for lab in labs:
    print(f"Lab {lab.id}: {lab.name}")
    parts = lab.parts.all()
    print(f"  Parts: {parts.count()}")
    
    for part in parts:
        print(f"    Part {part.id}: {part.name}")
        criteria = part.quality_criteria.all()
        print(f"      Criteria: {criteria.count()}")
        
        for criterion in criteria:
            print(f"        Criterion {criterion.id}: {criterion.name} (Max: {criterion.max_points}, Weight: {criterion.weight})")