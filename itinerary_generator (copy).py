from openai import OpenAI
import os
import logging
from datetime import datetime
from functools import wraps
import time
from flask_login import current_user

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

# Rate limiting
MAX_CALLS_PER_MINUTE = 50
call_history = []


def rate_limit_check():
    """Check if we've exceeded our rate limit"""
    now = datetime.now()
    # Remove calls older than 1 minute
    global call_history
    call_history = [t for t in call_history if (now - t).seconds < 60]
    if len(call_history) >= MAX_CALLS_PER_MINUTE:
        return False
    call_history.append(now)
    return True


def retry_with_exponential_backoff(func):

    @wraps(func)
    def wrapper(*args, **kwargs):
        for attempt in range(MAX_RETRIES):
            try:
                if not rate_limit_check():
                    raise Exception(
                        "Rate limit exceeded. Please try again later.")
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    raise e
                wait_time = (2**attempt) * RETRY_DELAY
                logger.warning(
                    f"Attempt {attempt + 1} failed. Waiting {wait_time} seconds..."
                )
                time.sleep(wait_time)
        return None

    return wrapper


def is_openai_available():
    """Check if OpenAI API is available and configured."""
    return bool(OPENAI_API_KEY)


def validate_api_key(api_key):
    """Validate OpenAI API key format"""
    if not isinstance(api_key, str) or len(api_key) < 20:
        raise ValueError("Invalid API key format")


@retry_with_exponential_backoff
def generate_itinerary(form_data):
    if not is_openai_available():
        raise Exception("OpenAI API is not available. Please try again later.")

    try:
        validate_api_key(OPENAI_API_KEY)
        openai_client = OpenAI(api_key=OPENAI_API_KEY)

        # Get destination name from choices
        destination = dict(form_data.destinations.choices).get(
            form_data.destinations.data)

        # Get travel focuses from the MultiCheckboxField
        travel_focus_dict = dict(form_data.travel_focus.choices)
        travel_focuses = [
            travel_focus_dict[focus] for focus in form_data.travel_focus.data
        ]

        # Add citizenship to the debug logging
        logger.debug(f"Citizenship: {form_data.citizenship.data}")

        # Handle specific locations
        specific_locations = form_data.specific_locations.data.strip(
        ) if form_data.specific_locations.data else None
        locations_prompt = f"\nSpecific places to include: {specific_locations}" if specific_locations else ""

        dietary_preferences = []
        if form_data.halal_food.data:
            dietary_preferences.append("Halal food required")
        if form_data.vegan_food.data:
            dietary_preferences.append("Vegan food required")

        accessibility_prompt = ""
        if form_data.wheelchair_accessible.data:
            accessibility_prompt = """
            Wheelchair Accessibility Requirements:
            - Include detailed accessibility information for each location
            - Prioritize wheelchair-accessible attractions and restaurants
            - Provide information about accessible transportation options
            - Note any potential accessibility challenges or alternate routes
            - Include details about accessible restrooms and facilities
            """

        # Calculate total travelers and travel duration
        total_travelers = (form_data.num_adults.data +
                           form_data.num_youth.data +
                           form_data.num_children.data)
        duration = (form_data.end_date.data -
                    form_data.start_date.data).days + 1

        # Budget breakdown calculations
        daily_budget = form_data.budget.data / duration
        per_person_budget = form_data.budget.data / total_travelers

        prompt = f"""Create a detailed international travel itinerary for {form_data.citizenship.data.replace('_', ' ').title()} travelers visiting {destination}{locations_prompt} with the following details:

Travel Group & Duration:
- Adults (18+): {form_data.num_adults.data}
- Youth (12-17): {form_data.num_youth.data}
- Children (2-11): {form_data.num_children.data}
- Infants (under 2): {form_data.num_infants.data}
- Duration: {duration} days ({form_data.start_date.data} to {form_data.end_date.data})

1. Comprehensive Price Breakdown:
   a) Transportation:
      - Flight costs by route with peak/off-peak variations
      - Airport transfer options and costs
      - Local transportation passes and costs
      - Taxi/ride-sharing estimates
      - Inter-city travel expenses
   
   b) Accommodation:
      - Hotel rates by area/district
      - Peak vs. off-peak pricing
      - Additional fees (tourism tax, service charge)
      - Family room availability and pricing
      - Accessible room options and costs
   
   c) Daily Expenses:
      - Meal costs by cuisine type (local vs. international)
      - Activity and entrance fees with age-based pricing
      - Shopping estimates by district
      - Entertainment costs
      - Prayer facility locations and any associated costs

2. Travel Requirements:
   a) Documentation:
      - Detailed visa requirements for {form_data.citizenship.data.replace('_', ' ').title()} passport holders
      - Processing time and fees
      - Required supporting documents
      - Embassy/consulate locations and contact details
   
   b) Health & Safety:
      - Required and recommended vaccinations
      - Travel insurance recommendations
      - Local healthcare facilities and costs
      - Emergency numbers and procedures
   
   c) Transportation:
      - Public transport system overview
      - Special passes and tourist cards
      - Accessibility options
      - Peak hours and service frequency
   
   d) Weather & Seasonal Considerations:
      - Monthly weather patterns
      - Best times to visit
      - Seasonal events and festivals
      - Clothing recommendations
   
   e) Cultural Guidelines:
      - Local customs and etiquette
      - Religious considerations
      - Dress code requirements
      - Tipping practices
      - Cultural taboos to avoid

3. Cost Optimization:
   a) Currency & Payments:
      - Current exchange rates (MYR to local currency)
      - Recommended payment methods
      - ATM availability and fees
      - Credit card acceptance
   
   b) Pricing Variations:
      - Peak vs. off-peak season differences
      - Group discount opportunities
      - Age-based discounts (child/senior/student)
      - Early booking benefits
   
   c) Money-Saving Strategies:
      - Tourist passes and city cards
      - Combination ticket options
      - Free walking tours and activities
      - Budget accommodation alternatives
      - Local market shopping tips

4. Location-Specific Information:
   a) Cultural Events:
      - Local festivals during visit period
      - Special events and exhibitions
      - Traditional performances
      - Cultural workshops
   
   b) Religious Facilities:
      - Nearby mosques and prayer rooms
      - Prayer times and facilities
      - Halal restaurants and certification details
      - Religious etiquette guidelines
   
   c) Accessibility Information:
      - Wheelchair access at attractions
      - Accessible transportation options
      - Special assistance services
      - Accessible restroom locations
   
   d) Family Services:
      - Baby changing facilities
      - Family rest areas
      - Child-friendly attractions
      - Kids' meal options
      - Stroller rental services
   
   e) Emergency Services:
      - Hospital locations and specialties
      - 24-hour pharmacies
      - Police stations
      - {form_data.citizenship.data.replace('_', ' ').title()} embassy/consulate details
      - Tourist police contacts

5. Daily Itinerary Structure:
   For each day, provide:
   - Detailed timeline with flexibility options
   - Distance and travel time between locations
   - Meal recommendations with dietary considerations
   - Activity costs and booking requirements
   - Weather-dependent alternatives
   - Rest and prayer break timings
   - Accessibility notes for each location
   - Family-friendly facilities available
   - Local transport options and costs

Budget Analysis:
- Total Budget: MYR {form_data.budget.data:,.2f}
- Daily Budget: MYR {daily_budget:,.2f}
- Per Person Budget: MYR {per_person_budget:,.2f}
- Includes Flights: {'Yes' if form_data.include_flights.data else 'No'}
- Includes Accommodation: {'Yes' if form_data.include_accommodation.data else 'No'}

Travel Preferences:
- Focus Areas: {', '.join(travel_focuses)}
- Accommodation Location: {form_data.accommodation_location.data}
- Accommodation Name: {form_data.accommodation_name.data}
- Travel Buddy Service: {'Requested' if form_data.need_guide.data else 'Not requested'}
- Dietary Requirements: {', '.join(dietary_preferences) if dietary_preferences else 'No specific dietary requirements'}
{accessibility_prompt}

Please provide all costs in both local currency and MYR, including low-budget alternatives and premium options where available. Ensure all recommendations consider the group composition and specific needs (dietary, accessibility, family-friendly, etc.)."""

        logger.debug("Generating itinerary with preferences:")
        logger.debug(f"Destination: {destination}")
        logger.debug(f"Specific Locations: {specific_locations}")
        logger.debug(f"Travel Focus: {travel_focuses}")
        logger.debug(f"Budget: MYR {form_data.budget.data}")
        logger.debug(f"Start Date: {form_data.start_date.data}")
        logger.debug(f"End Date: {form_data.end_date.data}")
        logger.debug(f"Dietary Preferences: {dietary_preferences}")
        logger.debug(
            f"Wheelchair Accessible: {form_data.wheelchair_accessible.data}")

        # Select OpenAI model based on subscription tier
        model = "gpt-4" if current_user.can_use_gpt4 else "gpt-3.5-turbo"
        logger.debug(
            f"Using model: {model} based on subscription tier: {current_user.subscription_tier}"
        )

        response = openai_client.chat.completions.create(
            model=model,
            messages=[{
                "role":
                "system",
                "content":
                f"You are an expert travel planner specializing in creating detailed itineraries for {form_data.citizenship.data.replace('_', ' ').title()} citizens visiting international destinations. You have extensive knowledge of visa requirements, cultural considerations, halal travel requirements, accessibility information, and budget optimization worldwide. Provide specific, actionable advice with exact prices and detailed breakdowns."
            }, {
                "role": "user",
                "content": prompt
            }],
            temperature=0.7,
            max_tokens=4000,
            top_p=0.95)

        logger.debug("Successfully received response from OpenAI")
        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"Error generating itinerary: {str(e)}")
        error_message = """
        We apologize, but we encountered an error while generating your itinerary. 
        This could be due to:
        - Temporary service unavailability
        - Invalid input parameters
        - Network connectivity issues
        
        Please try again in a few moments. If the problem persists, contact support.
        """
        raise Exception(error_message)
