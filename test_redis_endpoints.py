import unittest
import json
import redis
import os
from unittest.mock import Mock, patch
from cache_manager import CacheManager
from decimal import Decimal

class TestRedisEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test environment - runs once before all tests"""
        cls.cache_manager = CacheManager()
        # Ensure we're using test Redis instance
        os.environ['UPSTASH_REDIS_URL'] = 'redis://localhost:6380'

    def setUp(self):
        """Runs before each test"""
        # Clear Redis before each test
        if self.cache_manager.redis:
            self.cache_manager.clear_all()

    def test_get_exchange_rates(self):
        """Test getting all exchange rates from Redis"""
        # Prepare test data
        test_rates = {
            'USD': '1.0',
            'EUR': '0.85',
            'GBP': '0.73',
            'JPY': '110.0'
        }

        # Store test data in Redis
        self.cache_manager.set_currency_rates(test_rates)

        # Get rates and verify
        stored_rates = self.cache_manager.get_currency_rates()
        self.assertIsNotNone(stored_rates)
        self.assertEqual(stored_rates, test_rates)

    def test_store_specific_rate(self):
        """Test storing a specific exchange rate"""
        from_currency = 'USD'
        to_currency = 'EUR'
        rate = '0.85'

        # Store rate
        self.cache_manager.set_currency_rate(from_currency, to_currency, rate)

        # Verify stored rate
        stored_rate = self.cache_manager.get_currency_rate(from_currency, to_currency)
        self.assertEqual(stored_rate, rate)

    def test_rate_expiration(self):
        """Test that rates expire correctly"""
        from_currency = 'USD'
        to_currency = 'EUR'
        rate = '0.85'

        # Store rate with 1 second expiration
        self.cache_manager.set_currency_rate(from_currency, to_currency, rate, timeout=1)

        # Verify rate exists
        self.assertIsNotNone(self.cache_manager.get_currency_rate(from_currency, to_currency))

        # Wait for expiration
        import time
        time.sleep(2)

        # Verify rate has expired
        self.assertIsNone(self.cache_manager.get_currency_rate(from_currency, to_currency))

    def test_needs_rate_update(self):
        """Test rate update check functionality"""
        # Initially should need update
        self.assertTrue(self.cache_manager.needs_rate_update())

        # Set rates
        test_rates = {'USD': '1.0', 'EUR': '0.85'}
        self.cache_manager.set_currency_rates(test_rates)

        # Should not need update immediately after setting
        self.assertFalse(self.cache_manager.needs_rate_update())

    def test_clear_currency_cache(self):
        """Test clearing currency cache"""
        # Set some test rates
        test_rates = {'USD': '1.0', 'EUR': '0.85'}
        self.cache_manager.set_currency_rates(test_rates)

        # Clear currency cache
        success = self.cache_manager.clear_currency_cache()
        self.assertTrue(success)

        # Verify rates are cleared
        stored_rates = self.cache_manager.get_currency_rates()
        self.assertIsNone(stored_rates)

    def test_batch_currency_operations(self):
        """Test getting multiple currency rates at once"""
        # Set multiple rates
        rates = {
            ('USD', 'EUR'): '0.85',
            ('USD', 'GBP'): '0.73',
            ('USD', 'JPY'): '110.0'
        }

        for (from_curr, to_curr), rate in rates.items():
            self.cache_manager.set_currency_rate(from_curr, to_curr, rate)

        # Get multiple rates at once
        currency_pairs = list(rates.keys())
        batch_rates = self.cache_manager.get_many_currency_rates(currency_pairs)

        # Verify all rates were retrieved correctly
        for pair, rate in rates.items():
            self.assertEqual(batch_rates[pair], rate)

    def test_redis_connection_failure(self):
        """Test handling of Redis connection failures"""
        # Simulate Redis connection failure
        with patch.object(self.cache_manager, 'redis', None):
            # Verify operations return appropriate values on failure
            self.assertIsNone(self.cache_manager.get_currency_rates())
            self.assertTrue(self.cache_manager.needs_rate_update())
            self.assertFalse(self.cache_manager.set_currency_rates({'USD': '1.0'}))

    def tearDown(self):
        """Runs after each test"""
        if self.cache_manager.redis:
            self.cache_manager.clear_all()

if __name__ == '__main__':
    unittest.main()