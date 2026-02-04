"""Migration script to update statuses and parse notes for rejection stages."""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from backend.models import SessionLocal, Application, ApplicationStatus


def migrate_old_statuses(db):
    """Migrate old status values to new ones in PostgreSQL."""
    # First, add the new enum values if they don't exist
    new_values = ['first_interview', 'second_interview', 'third_interview']
    for val in new_values:
        try:
            db.execute(text(f"ALTER TYPE applicationstatus ADD VALUE IF NOT EXISTS '{val}'"))
            db.commit()
        except Exception as e:
            print(f"  Note: {val} - {e}")
            db.rollback()
    
    # Mapping from old status values to new ones
    status_mapping = {
        'phone_screen': 'first_interview',
        'technical_interview': 'second_interview', 
        'onsite_interview': 'third_interview',
        'final_interview': 'third_interview',  # Map final to third
    }
    
    updated = 0
    for old_status, new_status in status_mapping.items():
        try:
            # Raw SQL update since the enum values have changed
            result = db.execute(
                text(f"UPDATE applications SET status = '{new_status}' WHERE status = '{old_status}'")
            )
            updated += result.rowcount
            db.commit()
        except Exception as e:
            print(f"  Note: {old_status} -> {new_status} - {e}")
            db.rollback()
    
    print(f"[OK] Migrated {updated} applications to new status values")
    return updated


def parse_notes_for_rejection_stage(db):
    """Parse notes field to extract rejection stage info."""
    # Patterns to look for in notes
    patterns = [
        (r'(?:rejected?\s+)?(?:after\s+)?(?:the\s+)?first\s+(?:interview|round)', 'After First Interview'),
        (r'(?:rejected?\s+)?(?:after\s+)?(?:the\s+)?1st\s+(?:interview|round)', 'After First Interview'),
        (r'(?:rejected?\s+)?(?:after\s+)?(?:the\s+)?second\s+(?:interview|round)', 'After Second Interview'),
        (r'(?:rejected?\s+)?(?:after\s+)?(?:the\s+)?2nd\s+(?:interview|round)', 'After Second Interview'),
        (r'(?:rejected?\s+)?(?:after\s+)?(?:the\s+)?third\s+(?:interview|round)', 'After Third Interview'),
        (r'(?:rejected?\s+)?(?:after\s+)?(?:the\s+)?3rd\s+(?:interview|round)', 'After Third Interview'),
        (r'(?:rejected?\s+)?(?:after\s+)?(?:the\s+)?final\s+(?:interview|round)', 'After Third Interview'),
        (r'(?:rejected?\s+)?(?:after\s+)?(?:the\s+)?phone\s+(?:screen|interview)', 'After First Interview'),
        (r'(?:rejected?\s+)?(?:after\s+)?(?:the\s+)?technical\s+(?:interview|round)', 'After Second Interview'),
        (r'(?:rejected?\s+)?(?:after\s+)?(?:the\s+)?onsite\s+(?:interview|round)', 'After Third Interview'),
        (r'(?:rejected?\s+)?(?:after\s+)?(?:the\s+)?on-site\s+(?:interview|round)', 'After Third Interview'),
        (r'(?:rejected?\s+)?(?:at\s+)?(?:the\s+)?resume\s+(?:screen|stage)', 'Application/Resume Stage'),
        (r'(?:rejected?\s+)?(?:at\s+)?(?:the\s+)?application\s+(?:stage|review)', 'Application/Resume Stage'),
        (r'no\s+(?:response|reply)', 'Application/Resume Stage'),
    ]
    
    # Get all rejected applications without a rejection stage set
    rejected_apps = db.query(Application).filter(
        Application.status == ApplicationStatus.REJECTED,
        Application.notes.isnot(None)
    ).all()
    
    updated = 0
    for app in rejected_apps:
        if app.rejected_at_stage:
            # Already has a stage set, skip
            continue
            
        notes_lower = app.notes.lower() if app.notes else ''
        
        for pattern, stage in patterns:
            if re.search(pattern, notes_lower, re.IGNORECASE):
                app.rejected_at_stage = stage
                updated += 1
                print(f"  - {app.company_name}: Set rejection stage to '{stage}'")
                break
    
    print(f"[OK] Updated {updated} applications with rejection stage from notes")
    return updated


def migrate_old_rejection_stages(db):
    """Migrate old rejection stage values to new ones."""
    # Mapping from old rejection stage values to new ones
    stage_mapping = {
        'After Phone Screen': 'After First Interview',
        'After Technical Interview': 'After Second Interview',
        'After Onsite Interview': 'After Third Interview',
        'After Final Interview': 'After Third Interview',
    }
    
    updated = 0
    for app in db.query(Application).filter(Application.rejected_at_stage.isnot(None)).all():
        if app.rejected_at_stage in stage_mapping:
            old_stage = app.rejected_at_stage
            app.rejected_at_stage = stage_mapping[old_stage]
            updated += 1
            print(f"  - {app.company_name}: '{old_stage}' → '{app.rejected_at_stage}'")
    
    print(f"[OK] Migrated {updated} rejection stage values")
    return updated


def main():
    print("=" * 60)
    print("Status Migration Script")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Step 1: Migrate old status values
        print("\n[1/3] Migrating old status values...")
        migrate_old_statuses(db)
        
        # Step 2: Migrate old rejection stage values
        print("\n[2/3] Migrating old rejection stage values...")
        migrate_old_rejection_stages(db)
        
        # Step 3: Parse notes for rejection stages
        print("\n[3/3] Parsing notes for rejection stages...")
        parse_notes_for_rejection_stage(db)
        
        # Commit all changes
        db.commit()
        print("\n" + "=" * 60)
        print("[SUCCESS] Migration completed!")
        print("=" * 60)
        
    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
