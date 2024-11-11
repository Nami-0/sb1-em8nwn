import sys
import os
# Add the parent directory to Python path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app, db
from models import User, AccessViolation
from sqlalchemy import text, inspect

def upgrade():
    app = create_app()
    with app.app_context():
        # Add is_admin column to User table if it doesn't exist
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE'))
        
        # Create AccessViolation table if it doesn't exist
        inspector = inspect(db.engine)
        if 'access_violation' not in inspector.get_table_names():
            AccessViolation.__table__.create(db.engine)
            
        db.session.commit()

if __name__ == '__main__':
    upgrade()
