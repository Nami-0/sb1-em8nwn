import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app, db
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def upgrade():
    app = create_app()
    with app.app_context():
        try:
            # Add citizenship column to itinerary table
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE itinerary ADD COLUMN IF NOT EXISTS citizenship VARCHAR(100) DEFAULT \'malaysia\''))
            db.session.commit()
            logger.info("Successfully added citizenship column to itinerary table")
        except Exception as e:
            logger.error(f"Error adding citizenship column: {str(e)}")
            db.session.rollback()
            raise e

if __name__ == '__main__':
    upgrade()