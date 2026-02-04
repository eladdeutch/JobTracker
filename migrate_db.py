"""Add new columns to existing database."""
import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from backend.models.database import engine

def migrate():
    """Add rejected_at_stage columns to applications and emails tables."""
    
    with engine.connect() as conn:
        # Check and add column to applications table
        try:
            conn.execute(text("""
                ALTER TABLE applications 
                ADD COLUMN IF NOT EXISTS rejected_at_stage VARCHAR(100)
            """))
            print("✓ Added rejected_at_stage to applications table")
        except Exception as e:
            print(f"Applications table: {e}")
        
        # Check and add column to emails table
        try:
            conn.execute(text("""
                ALTER TABLE emails 
                ADD COLUMN IF NOT EXISTS rejected_at_stage VARCHAR(100)
            """))
            print("✓ Added rejected_at_stage to emails table")
        except Exception as e:
            print(f"Emails table: {e}")
        
        conn.commit()
        print("\n✓ Migration complete!")

if __name__ == '__main__':
    migrate()
