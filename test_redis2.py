from redis_helper import test_redis_connection
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

# Run the test
if __name__ == "__main__":
    print("Testing Redis connection...")
    result = test_redis_connection()
    if result:
        print("✅ Redis connection is working correctly!")
    else:
        print("❌ Redis connection test failed!")