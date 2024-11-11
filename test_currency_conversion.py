import unittest
from decimal import Decimal
from unittest.mock import Mock, patch
from cache_manager import CacheManager
from currency_data import format_currency, get_currency_info

class TestCurrencyConversion(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.cache_manager = CacheManager()
        self.test_rates = {
            'MYR': '1.0',
            'USD': '0.24',
            'EUR': '0.20',
            'GBP': '0.18',
            'JPY': '26.5'
        }
        # Store test rates in cache
        self.cache_manager.set_currency_rates(self.test_rates)

    def test_currency_formatting(self):
        """Test currency amount formatting"""
        test_cases = [
            ('USD', 1000.50, '$1,000.50'),
            ('JPY', 1000.50, '¥1,000'),  # JPY rounds to whole numbers
            ('MYR', 1000.50, 'RM1,000.50'),
            ('EUR', 1000.50, '€1,000.50')
        ]

        for currency, amount, expected in test_cases:
            formatted = format_currency(Decimal(str(amount)), currency)
            self.assertEqual(formatted, expected)

    def test_currency_conversion(self):
        """Test basic currency conversion"""
        amount = Decimal('100')

        # Test MYR to USD
        usd_rate = Decimal(self.test_rates['USD'])
        expected_usd = amount * usd_rate
        converted_usd = self.convert_currency(amount, 'MYR', 'USD')
        self.assertEqual(converted_usd, expected_usd)

        # Test MYR to EUR
        eur_rate = Decimal(self.test_rates['EUR'])
        expected_eur = amount * eur_rate
        converted_eur = self.convert_currency(amount, 'MYR', 'EUR')
        self.assertEqual(converted_eur, expected_eur)

    def test_cross_currency_conversion(self):
        """Test conversion between non-base currencies"""
        amount = Decimal('100')

        # Test USD to EUR
        usd_rate = Decimal(self.test_rates['USD'])
        eur_rate = Decimal(self.test_rates['EUR'])
        expected_rate = eur_rate / usd_rate

        converted = self.convert_currency(amount, 'USD', 'EUR')
        expected = amount * expected_rate

        self.assertAlmostEqual(float(converted), float(expected), places=2)

    def test_same_currency_conversion(self):
        """Test conversion within same currency"""
        amount = Decimal('100')
        converted = self.convert_currency(amount, 'USD', 'USD')
        self.assertEqual(converted, amount)

    def test_invalid_currency_conversion(self):
        """Test conversion with invalid currency codes"""
        amount = Decimal('100')

        with self.assertRaises(ValueError):
            self.convert_currency(amount, 'INVALID', 'USD')

        with self.assertRaises(ValueError):
            self.convert_currency(amount, 'USD', 'INVALID')

    def test_zero_amount_conversion(self):
        """Test conversion of zero amount"""
        converted = self.convert_currency(Decimal('0'), 'USD', 'EUR')
        self.assertEqual(converted, Decimal('0'))

    def test_negative_amount_conversion(self):
        """Test conversion of negative amounts"""
        amount = Decimal('-100')
        converted = self.convert_currency(amount, 'USD', 'EUR')
        self.assertTrue(converted < 0)

    def test_large_amount_conversion(self):
        """Test conversion of large amounts"""
        amount = Decimal('1000000')
        converted = self.convert_currency(amount, 'USD', 'EUR')
        self.assertIsInstance(converted, Decimal)

    def convert_currency(self, amount, from_currency, to_currency):
        """Helper method to convert currency using cached rates"""
        if from_currency not in self.test_rates or to_currency not in self.test_rates:
            raise ValueError("Invalid currency code")

        if from_currency == to_currency:
            return amount

        # Convert through base currency (MYR)
        from_rate = Decimal(self.test_rates[from_currency])
        to_rate = Decimal(self.test_rates[to_currency])

        # First convert to MYR, then to target currency
        myr_amount = amount / from_rate
        converted = myr_amount * to_rate

        return converted.quantize(Decimal('.01'))

    def tearDown(self):
        """Clean up after tests"""
        if self.cache_manager.redis:
            self.cache_manager.clear_all()

if __name__ == '__main__':
    unittest.main()