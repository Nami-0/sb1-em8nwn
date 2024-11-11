import redis
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_redis_connection():
    """Test Redis connection and print status"""
    try:
        # Try to connect to Redis
        r = redis.Redis(
            host='localhost',
            port=6380,
            socket_timeout=5,
            socket_connect_timeout=5,
            decode_responses=True
        )

        # Test the connection with a ping
        response = r.ping()
        logger.info(f"Redis connection test successful! Response: {response}")

        # Try to set and get a value
        r.set('test_key', 'test_value')
        value = r.get('test_key')
        logger.info(f"Redis set/get test successful! Retrieved value: {value}")

        # Clean up
        r.delete('test_key')

        return True

    except redis.ConnectionError as e:
        logger.error(f"Could not connect to Redis: {str(e)}")
        logger.info("Please make sure Redis server is running on port 6380")
        return False

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return False

if __name__ == "__main__":
    print("Testing Redis connection...")
    test_redis_connection()