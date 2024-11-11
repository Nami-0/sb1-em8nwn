import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app, db
from models import User
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def upgrade():
    app = create_app()
    with app.app_context():
        try:
            # Get the first user in the system to update
            user = User.query.first()
            if user:
                logger.info(f"Updating subscription tier for user {user.email}")
                user.subscription_tier = 'gold_wanderer'
                db.session.commit()
                logger.info("Successfully updated subscription tier to Gold Wanderer")
            else:
                logger.warning("No users found in the database")
        except Exception as e:
            logger.error(f"Error updating subscription tier: {str(e)}")
            db.session.rollback()

if __name__ == '__main__':
    upgrade()
