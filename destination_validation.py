import logging
from decimal import Decimal
from cache_manager import CacheManager, cache_enabled
from currency_data import format_currency, get_currency_info

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize cache manager
cache_manager = CacheManager()

# Constants
TRAVEL_BUDDY_COST_PER_DAY = Decimal('500')  # Base cost in MYR per day

# Dictionary defining minimum budget (MYR) per destination
DESTINATION_RULES = {
    'japan': {
        'min_budget_per_day': {
            'base': Decimal('200'),  # Base expenses (food, local transport, activities)
            'accommodation': Decimal('200'),  # Additional for accommodation
            'flights': Decimal('400'),  # Additional for flights (amortized per day)
        },
        'local_currency': 'JPY',
        'budget_message': lambda incl_flights, incl_accom, with_buddy, currency_code: (
            f"For Japan, we recommend a minimum daily budget of "
            f"{format_currency(200, currency_code)} for basic expenses"
            f"{', plus ' + format_currency(200, currency_code) + ' for accommodation' if incl_accom else ''}"
            f"{', plus ' + format_currency(400, currency_code) + ' for flights' if incl_flights else ''}"
            f"{', plus ' + format_currency(500, currency_code) + ' for travel buddy' if with_buddy else ''} "
            f"per person."
        )
    },
    'south_korea': {
        'min_budget_per_day': {
            'base': Decimal('180'),
            'accommodation': Decimal('180'),
            'flights': Decimal('350'),
        },
        'local_currency': 'KRW',
        'budget_message': lambda incl_flights, incl_accom, with_buddy, currency_code: (
            f"For South Korea, we recommend a minimum daily budget of "
            f"{format_currency(180, currency_code)} for basic expenses"
            f"{', plus ' + format_currency(180, currency_code) + ' for accommodation' if incl_accom else ''}"
            f"{', plus ' + format_currency(350, currency_code) + ' for flights' if incl_flights else ''}"
            f"{', plus ' + format_currency(500, currency_code) + ' for travel buddy' if with_buddy else ''} "
            f"per person."
        )
    }
}

# Default rules for destinations not specifically listed
DEFAULT_RULES = {
    'min_budget_per_day': {
        'base': Decimal('150'),
        'accommodation': Decimal('150'),
        'flights': Decimal('300'),
    },
    'budget_message': lambda incl_flights, incl_accom, with_buddy, currency_code: (
        f"We recommend a minimum daily budget of "
        f"{format_currency(150, currency_code)} for basic expenses"
        f"{', plus ' + format_currency(150, currency_code) + ' for accommodation' if incl_accom else ''}"
        f"{', plus ' + format_currency(300, currency_code) + ' for flights' if incl_flights else ''}"
        f"{', plus ' + format_currency(500, currency_code) + ' for travel buddy' if with_buddy else ''} "
        f"per person."
    )
}

@cache_enabled
def get_destination_rules(destination):
    """Get validation rules for a specific destination with caching."""
    cache_key = f"destination_rules:{destination}"

    # Try to get from cache first
    cached_rules = cache_manager.get(cache_key)
    if cached_rules:
        return cached_rules

    # If not in cache, get rules and cache them
    rules = DESTINATION_RULES.get(destination, DEFAULT_RULES)
    cache_manager.set(cache_key, rules, timeout=86400)  # Cache for 24 hours

    return rules

def calculate_min_budget_per_day(rules, include_flights, include_accommodation, need_buddy):
    """Calculate minimum budget per day based on included items."""
    min_budget = rules['min_budget_per_day']['base']
    if include_accommodation:
        min_budget += rules['min_budget_per_day']['accommodation']
    if include_flights:
        min_budget += rules['min_budget_per_day']['flights']
    if need_buddy:
        min_budget += TRAVEL_BUDDY_COST_PER_DAY
    return min_budget

def convert_currency_if_needed(amount, from_currency, to_currency):
    """Convert amount between currencies if needed."""
    if from_currency == to_currency:
        return amount

    # Get exchange rate from cache or API
    cache_key = f"exchange_rate:{from_currency}:{to_currency}"
    rate = cache_manager.get(cache_key)

    if not rate:
        # TODO: Implement actual exchange rate API call
        rate = Decimal('1.0')  # Default to 1.0 for now
        cache_manager.set(cache_key, str(rate), timeout=3600)  # Cache for 1 hour

    return amount * Decimal(str(rate))

@cache_enabled
def validate_budget_and_duration(destination, budget, num_people, start_date, end_date, 
                               include_flights=True, include_accommodation=True, 
                               need_buddy=False, currency_code='MYR'):
    """
    Validate if the budget and duration are reasonable for the destination.
    Duration check is performed first, followed by budget validation if duration is valid.
    Now supports different currencies.
    """
    # Duration validation first
    duration = (end_date - start_date).days + 1
    logger.debug(f"Duration validation check: {duration} days")

    # Skip validation for 'surprise_me' option
    if destination == 'surprise_me':
        return True, []

    # 7-day duration limit check
    if duration > 7:
        logger.debug("Duration validation result: Failed")
        return False, ["Currently, we only support itineraries up to 7 days. We are working on supporting longer durations in future updates."]

    logger.debug("Duration validation result: Passed")

    # Budget validation
    rules = get_destination_rules(destination)
    budget_per_person_per_day = Decimal(str(budget)) / (Decimal(str(num_people)) * Decimal(str(duration)))

    # Convert budget to MYR for comparison if needed
    if currency_code != 'MYR':
        budget_per_person_per_day = convert_currency_if_needed(
            budget_per_person_per_day, 
            currency_code, 
            'MYR'
        )

    # Add debug logging
    logger.debug(f"Validating budget for {destination}:")
    logger.debug(f"Budget per person per day: {currency_code} {budget_per_person_per_day:.2f}")
    min_budget_per_day = calculate_min_budget_per_day(rules, include_flights, include_accommodation, need_buddy)
    logger.debug(f"Required minimum budget: MYR {min_budget_per_day:.2f}")

    messages = []
    is_valid = True

    # Validate budget
    if budget_per_person_per_day < min_budget_per_day:
        logger.debug("Budget validation failed")
        messages.append(
            rules.get('budget_message', DEFAULT_RULES['budget_message'])(
                include_flights, 
                include_accommodation, 
                need_buddy,
                currency_code
            )
        )
        is_valid = False

    logger.debug(f"Validation result - Valid: {is_valid}, Messages: {messages}")    
    return is_valid, messages

def get_recommended_budget(destination, duration, num_people, include_flights=True, 
                         include_accommodation=True, need_buddy=False, currency_code='MYR'):
    """Get recommended budget for the destination."""
    rules = get_destination_rules(destination)
    min_budget_per_day = calculate_min_budget_per_day(rules, include_flights, include_accommodation, need_buddy)

    # Calculate total minimum budget in MYR
    total_budget_myr = min_budget_per_day * Decimal(str(duration)) * Decimal(str(num_people))

    # Convert to requested currency if needed
    if currency_code != 'MYR':
        total_budget = convert_currency_if_needed(total_budget_myr, 'MYR', currency_code)
    else:
        total_budget = total_budget_myr

    return {
        'total_budget': total_budget,
        'per_day': total_budget / Decimal(str(duration)),
        'per_person': total_budget / Decimal(str(num_people)),
        'per_person_per_day': total_budget / (Decimal(str(duration)) * Decimal(str(num_people))),
        'currency': currency_code
    }

def get_destination_currency(destination):
    """Get the local currency for a destination."""
    return DESTINATION_RULES.get(destination, {}).get('local_currency', 'USD')