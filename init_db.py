from app import create_app
from extensions import db
from sqlalchemy import inspect
import logging
import os
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_up_files():
    """Clean up old database and session files."""
    try:
        # Remove old database file
        if os.path.exists('instance/app.db'):
            os.remove('instance/app.db')
            logger.info("Removed old database file")

        # Remove old session files
        if os.path.exists('flask_session'):
            shutil.rmtree('flask_session')
            logger.info("Removed old session files")

        # Remove __pycache__ directories
        for root, dirs, files in os.walk('.'):
            if '__pycache__' in dirs:
                cache_path = os.path.join(root, '__pycache__')
                shutil.rmtree(cache_path)
                logger.info(f"Removed __pycache__ from {root}")

    except Exception as e:
        logger.warning(f"Error during cleanup: {str(e)}")

def get_table_names(engine):
    """Get list of table names using inspector"""
    inspector = inspect(engine)
    return inspector.get_table_names()

def init_db():
    """Initialize the database with all tables."""
    try:
        # Clean up old files first
        clean_up_files()

        # Create Flask app
        app = create_app()

        # Use app context for database operations
        with app.app_context():
            # Drop all tables first
            logger.info("Dropping existing tables...")
            db.drop_all()

            # Create all tables with new schema
            db.create_all()
            logger.info("Created all tables successfully")

            # Verify tables were created
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"Created tables: {', '.join(tables)}")

            return True

    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        return False

if __name__ == '__main__':
    try:
        print("Starting database initialization...")
        success = init_db()
        if success:
            print("✅ Database initialized successfully!")
            app = create_app()
            with app.app_context():
                inspector = inspect(db.engine)
                print("Created tables:")
                for table in inspector.get_table_names():
                    print(f"  - {table}")
        else:
            print("❌ Database initialization failed!")
    except Exception as e:
        print(f"❌ Failed to initialize database: {str(e)}")
        exit(1)