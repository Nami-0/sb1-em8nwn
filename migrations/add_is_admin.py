from app import create_app, db
from models import User, AccessViolation
from sqlalchemy import text

def upgrade():
    app = create_app()
    with app.app_context():
        # Add is_admin column to User table if it doesn't exist
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE'))
        db.session.commit()

if __name__ == '__main__':
    upgrade()
