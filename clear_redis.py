from redis_helper import get_redis_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clear_all_redis_data():
    """Clear all Redis data."""
    try:
        redis_client = get_redis_connection()
        if redis_client:
            redis_client.flushall()
            logger.info("Successfully cleared all Redis data")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to clear Redis data: {str(e)}")
        return False

if __name__ == "__main__":
    print("Clearing Redis data...")
    if clear_all_redis_data():
        print("✅ Successfully cleared Redis data")
    else:
        print("❌ Failed to clear Redis data")