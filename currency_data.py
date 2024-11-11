from decimal import Decimal
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CurrencyInfo:
    code: str
    symbol: str
    name: str
    flag: str  # Unicode flag emoji
    position: str = 'before'  # 'before' or 'after' the amount
    decimal_places: int = 2
    thousands_separator: str = ','
    decimal_separator: str = '.'

# Comprehensive currency mapping
CURRENCY_DATA = {
    'MYR': CurrencyInfo('MYR', 'RM', 'Malaysian Ringgit', '🇲🇾'),
    'USD': CurrencyInfo('USD', '$', 'US Dollar', '🇺🇸'),
    'SGD': CurrencyInfo('SGD', 'S$', 'Singapore Dollar', '🇸🇬'),
    'JPY': CurrencyInfo('JPY', '¥', 'Japanese Yen', '🇯🇵', decimal_places=0),
    'KRW': CurrencyInfo('KRW', '₩', 'South Korean Won', '🇰🇷', decimal_places=0),
    'CNY': CurrencyInfo('CNY', '¥', 'Chinese Yuan', '🇨🇳'),
    'THB': CurrencyInfo('THB', '฿', 'Thai Baht', '🇹🇭'),
    'IDR': CurrencyInfo('IDR', 'Rp', 'Indonesian Rupiah', '🇮🇩', decimal_places=0),
    'AUD': CurrencyInfo('AUD', 'A$', 'Australian Dollar', '🇦🇺'),
    'NZD': CurrencyInfo('NZD', 'NZ$', 'New Zealand Dollar', '🇳🇿'),
    'GBP': CurrencyInfo('GBP', '£', 'British Pound', '🇬🇧'),
    'EUR': CurrencyInfo('EUR', '€', 'Euro', '🇪🇺'),
    'VND': CurrencyInfo('VND', '₫', 'Vietnamese Dong', '🇻🇳', decimal_places=0),
    'PHP': CurrencyInfo('PHP', '₱', 'Philippine Peso', '🇵🇭'),
    'HKD': CurrencyInfo('HKD', 'HK$', 'Hong Kong Dollar', '🇭🇰'),
    'TWD': CurrencyInfo('TWD', 'NT$', 'Taiwan Dollar', '🇹🇼'),
    'INR': CurrencyInfo('INR', '₹', 'Indian Rupee', '🇮🇳'),
    'AED': CurrencyInfo('AED', 'د.إ', 'UAE Dirham', '🇦🇪'),
    'SAR': CurrencyInfo('SAR', 'ر.س', 'Saudi Riyal', '🇸🇦', position='after'),
    'QAR': CurrencyInfo('QAR', 'ر.ق', 'Qatari Riyal', '🇶🇦', position='after'),
}

# Mapping of citizenship to default currency
CITIZENSHIP_TO_CURRENCY = {
    'malaysia': 'MYR',
    'singapore': 'SGD',
    'indonesia': 'IDR',
    'thailand': 'THB',
    'vietnam': 'VND',
    'philippines': 'PHP',
    'china': 'CNY',
    'japan': 'JPY',
    'south_korea': 'KRW',
    'india': 'INR',
    'australia': 'AUD',
    'new_zealand': 'NZD',
    'united_states': 'USD',
    'united_kingdom': 'GBP',
    'hong_kong': 'HKD',
    'taiwan': 'TWD',
    'united_arab_emirates': 'AED',
    'saudi_arabia': 'SAR',
    'qatar': 'QAR',
}

# Currency groups for common conversions
CURRENCY_GROUPS = {
    'ASEAN': ['MYR', 'SGD', 'THB', 'IDR', 'PHP', 'VND'],
    'East_Asia': ['JPY', 'KRW', 'CNY', 'HKD', 'TWD'],
    'Oceania': ['AUD', 'NZD'],
    'Western': ['USD', 'GBP', 'EUR'],
    'Middle_East': ['AED', 'SAR', 'QAR'],
}

def get_default_currency(citizenship: str) -> str:
    """Get the default currency for a given citizenship."""
    return CITIZENSHIP_TO_CURRENCY.get(citizenship.lower(), 'MYR')

def get_currency_info(currency_code: str) -> Optional[CurrencyInfo]:
    """Get currency information for a given currency code."""
    return CURRENCY_DATA.get(currency_code.upper())

def format_currency(amount: Decimal, currency_code: str) -> str:
    """Format amount in specified currency with proper formatting."""
    try:
        currency = CURRENCY_DATA[currency_code.upper()]

        # Format the number with proper decimal places
        formatted_number = f"{amount:,.{currency.decimal_places}f}"

        # Replace separators if different from default
        if currency.thousands_separator != ',':
            formatted_number = formatted_number.replace(',', currency.thousands_separator)
        if currency.decimal_separator != '.':
            formatted_number = formatted_number.replace('.', currency.decimal_separator)

        # Position the symbol correctly
        if currency.position == 'before':
            return f"{currency.symbol}{formatted_number}"
        return f"{formatted_number}{currency.symbol}"

    except KeyError:
        logger.error(f"Unknown currency code: {currency_code}")
        return f"{amount:,.2f} {currency_code}"
    except Exception as e:
        logger.error(f"Error formatting currency: {str(e)}")
        return str(amount)

def get_common_currencies() -> Dict[str, CurrencyInfo]:
    """Get list of commonly used currencies for the interface."""
    common_codes = ['MYR', 'USD', 'SGD', 'JPY', 'KRW', 'CNY', 'THB', 'IDR', 'AUD']
    return {code: CURRENCY_DATA[code] for code in common_codes}

def get_currency_group(currency_code: str) -> str:
    """Get the currency group for a given currency code."""
    for group, currencies in CURRENCY_GROUPS.items():
        if currency_code.upper() in currencies:
            return group
    return 'Other'

def get_currencies_in_group(group: str) -> list:
    """Get all currencies in a specific group."""
    return CURRENCY_GROUPS.get(group, [])

def validate_currency_code(currency_code: str) -> bool:
    """Validate if a currency code is supported."""
    return currency_code.upper() in CURRENCY_DATA

def get_currency_display_name(currency_code: str) -> str:
    """Get the full display name of a currency (e.g., 'MYR - Malaysian Ringgit')."""
    try:
        currency = CURRENCY_DATA[currency_code.upper()]
        return f"{currency.code} - {currency.name} {currency.flag}"
    except KeyError:
        return currency_code

def get_currency_symbol(currency_code: str) -> str:
    """Get the symbol for a currency code."""
    try:
        return CURRENCY_DATA[currency_code.upper()].symbol
    except KeyError:
        return currency_code

# Exchange rate related functions (to be implemented with your preferred forex API)
def get_exchange_rate(from_currency: str, to_currency: str) -> Decimal:
    """
    Get the exchange rate between two currencies.
    This is a placeholder - implement with your preferred forex API.
    """
    # TODO: Implement actual exchange rate fetching
    # For now, returns 1.0 if same currency, else raises error
    if from_currency.upper() == to_currency.upper():
        return Decimal('1.0')
    raise NotImplementedError("Exchange rate functionality not implemented")

def convert_currency(amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
    """
    Convert an amount from one currency to another.
    This is a placeholder - implement with your preferred forex API.
    """
    if from_currency.upper() == to_currency.upper():
        return amount
    rate = get_exchange_rate(from_currency, to_currency)
    return amount * rate

# Helper function for itinerary generation
def get_currency_disclaimer() -> str:
    """Get the currency disclaimer text for itineraries."""
    return """
    Note: All prices are approximate and subject to change. Currency conversions are based on 
    current exchange rates and may vary. It's recommended to check current rates before travel.
    """