import os
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from flask_login import current_user
from cache_manager import CacheManager, cache_enabled
from currency_data import format_currency, get_currency_info
from gpt_model_handler import GPTModelHandler

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

cache_manager = CacheManager()

def is_openai_available():
    """Check if OpenAI API is available and configured."""
    return bool(os.getenv('OPENAI_API_KEY'))

@cache_enabled
def generate_itinerary(form):
    """Generate a travel itinerary using appropriate GPT model with caching."""

    try:
        # Prepare request data for caching
        request_data = prepare_cache_data(form)

        # Check cache first
        cached_response = cache_manager.get_openai_response(request_data)
        if cached_response:
            logger.info("Using cached OpenAI response")
            return cached_response

        # Build system and user prompts
        system_prompt = build_system_prompt(form)
        user_prompt = build_detailed_prompt(form)

        # Get the appropriate model based on subscription
        logger.info(f"Using model {current_user.gpt_model_access} for user {current_user.id}")

        # Generate itinerary using appropriate model
        itinerary = GPTModelHandler.generate_itinerary(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7
        )

        # Cache the response
        cache_manager.cache_openai_response(request_data, itinerary)

        return itinerary

    except Exception as e:
        logger.error(f"Error generating itinerary: {str(e)}")
        error_message = f"""
        We apologize, but we encountered an error while generating your itinerary. 
        Error Details: {str(e)}

        This could be due to:
        - Temporary service unavailability
        - Invalid input parameters
        - Network connectivity issues

        Your subscription tier: {current_user.subscription_tier}
        Model access level: {current_user.gpt_model_access}

        Please try again in a few moments. If the problem persists, contact support.
        """
        raise Exception(error_message)

def prepare_cache_data(form):
    """Prepare request data for caching."""
    return {
        'citizenship': form.citizenship.data,
        'destination': form.destinations.data,
        'specific_locations': form.specific_locations.data,
        'travel_focus': form.travel_focus.data,
        'budget': float(form.budget.data),
        'currency': form.currency.data,
        'include_flights': form.include_flights.data,
        'include_accommodation': form.include_accommodation.data,
        'num_adults': form.num_adults.data,
        'num_youth': form.num_youth.data,
        'num_children': form.num_children.data,
        'num_infants': form.num_infants.data,
        'start_date': form.start_date.data.isoformat(),
        'end_date': form.end_date.data.isoformat(),
        'halal_food': form.halal_food.data,
        'vegan_food': form.vegan_food.data,
        'wheelchair_accessible': form.wheelchair_accessible.data,
        'need_guide': form.need_guide.data,
        'accommodation_location': form.accommodation_location.data,
        'accommodation_name': form.accommodation_name.data
    }

def build_system_prompt(form):
    """Build the system prompt with expertise focus"""
    current_time = datetime.now()
    currency_info = get_currency_info(form.currency.data)

    base_prompt = f"""You are an expert travel planner specializing in creating detailed itineraries for {form.citizenship.data.replace('_', ' ').title()} citizens, with real-time updates as of {current_time.strftime('%Y-%m-%d %H:%M')} {current_time.astimezone().tzname()}.

Your expertise includes:
1. Comprehensive Cost Analysis:
   - All prices in {currency_info.code}
   - Peak vs. off-peak pricing
   - Group discounts and special rates
   - Hidden costs and fees
   - Local tax implications

2. Cultural Intelligence:
   - Local customs and etiquette
   - Cultural sensitivities
   - Dress code requirements
   - Social norms and taboos
   - Festival and holiday impacts

3. Safety and Documentation:
   - Visa requirements and processes
   - Insurance recommendations
   - Emergency contacts and procedures
   - Local healthcare facilities
   - Travel advisories and warnings

4. Transportation Expertise:
   - Public transport systems
   - Private transfer options
   - Walking and cycling routes
   - Accessibility considerations
   - Traffic patterns and peak times

5. Time Management:
   - Opening hours and peak times
   - Seasonal variations
   - Queue management strategies
   - Optimal visit durations
   - Buffer time recommendations"""

    # Add religious considerations if halal food is required
    if form.halal_food.data:
        religious_prompt = """
6. Islamic Facilities:
   - Prayer times for each day
   - Mosque locations and accessibility
   - Prayer room facilities
   - Halal restaurant certifications
   - Wudu facilities
   - Qibla direction in accommodations"""
        base_prompt += religious_prompt

    base_prompt += """

For every location recommended:
1. Provide Google Maps link: [Location Name](https://www.google.com/maps/search/?api=1&query=encoded_location_name)
2. List exact opening hours and best visit times
3. Include real-time travel durations
4. Specify all costs in requested currency
5. Note accessibility features
6. List nearby amenities

Format Requirements:
1. Use 24-hour time format (e.g., 14:30)
2. Include day of week for all dates
3. Structure timing in 30-minute blocks
4. Provide exact travel durations
5. Include alternative options for weather
6. List exact costs with tax included"""

    return base_prompt

def build_detailed_prompt(form):
    """Build the detailed user prompt with all requirements"""
    currency_info = get_currency_info(form.currency.data)
    destination = dict(form.destinations.choices).get(form.destinations.data)

    # Calculate important values
    duration = (form.end_date.data - form.start_date.data).days + 1
    total_travelers = (form.num_adults.data + form.num_youth.data + form.num_children.data)
    daily_budget = form.budget.data / duration
    per_person_budget = form.budget.data / total_travelers

    # Get travel focuses
    travel_focus_dict = dict(form.travel_focus.choices)
    travel_focuses = [travel_focus_dict[focus] for focus in form.travel_focus.data]

    # Build initial prompt with travel group info
    prompt = f"""Create a detailed international travel itinerary for {form.citizenship.data.replace('_', ' ').title()} travelers visiting {destination} with the following specifications:

Travel Group Information:
1. Composition:
   - Adults (18+): {form.num_adults.data}
   - Youth (12-17): {form.num_youth.data}
   - Children (2-11): {form.num_children.data}
   - Infants (under 2): {form.num_infants.data}
   Total: {total_travelers} travelers

2. Travel Period:
   - Duration: {duration} days
   - Start: {form.start_date.data.strftime('%A, %Y-%m-%d')}
   - End: {form.end_date.data.strftime('%A, %Y-%m-%d')}

3. Budget Analysis (in {currency_info.code}):
   - Total Budget: {format_currency(form.budget.data, form.currency.data)}
   - Daily Budget: {format_currency(daily_budget, form.currency.data)}
   - Per Person Budget: {format_currency(per_person_budget, form.currency.data)}
   - Includes Flights: {'Yes' if form.include_flights.data else 'No'}
   - Includes Accommodation: {'Yes' if form.include_accommodation.data else 'No'}

4. Preferences:
   - Travel Focus: {', '.join(travel_focuses)}
   - Location Base: {form.accommodation_location.data}
   - Accommodation: {form.accommodation_name.data}
   - Guide Service: {'Requested' if form.need_guide.data else 'Not requested'}
   """

    # Add dietary requirements if specified
    dietary_prefs = []
    if form.halal_food.data:
        dietary_prefs.append("Halal food required")
    if form.vegan_food.data:
        dietary_prefs.append("Vegan food required")

    if dietary_prefs:
        prompt += f"   - Dietary Requirements: {', '.join(dietary_prefs)}\n"

    # Handle specific locations
    if form.specific_locations.data:
        prompt += f"\nRequested Locations to Include:\n{form.specific_locations.data}\n"

    return prompt

def build_price_breakdown_section(form):
    """Build the comprehensive price breakdown section of the prompt"""
    return """
1. Comprehensive Price Breakdown Required:
   a) Transportation Analysis:
      - Flight costs by route with peak/off-peak variations
      - Airport transfer options and costs
      - Local transportation passes and costs
      - Taxi/ride-sharing estimates
      - Inter-city travel expenses

   b) Accommodation Details:
      - Hotel rates by area/district
      - Peak vs. off-peak pricing
      - Additional fees (tourism tax, service charge)
      - Family room availability and pricing
      - Accessible room options and costs

   c) Daily Expense Breakdown:
      - Meal costs by cuisine type (local vs. international)
      - Activity and entrance fees with age-based pricing
      - Shopping estimates by district
      - Entertainment costs
      - Prayer facility locations and any associated costs

2. Cost Optimization Strategies:
   a) Currency & Payments:
      - Current exchange rates
      - Recommended payment methods
      - ATM availability and fees
      - Credit card acceptance

   b) Pricing Variations:
      - Peak vs. off-peak season differences
      - Group discount opportunities
      - Age-based discounts (child/senior/student)
      - Early booking benefits

   c) Money-Saving Tips:
      - Tourist passes and city cards
      - Combination ticket options
      - Free walking tours and activities
      - Budget accommodation alternatives
      - Local market shopping tips"""

def build_requirements_section(form):
    """Build the travel requirements and cultural information section"""
    return f"""
3. Travel Requirements:
   a) Documentation:
      - Detailed visa requirements for {form.citizenship.data.replace('_', ' ').title()} passport holders
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

4. Location-Specific Information:
   a) Cultural Events:
      - Local festivals during visit period
      - Special events and exhibitions
      - Traditional performances
      - Cultural workshops
   """
def build_religious_accessibility_section(form):
    """Build the religious and accessibility features section if applicable"""
    # Start with base accessibility info
    section = """
   b) Accessibility Information:
      - Wheelchair access at attractions
      - Accessible transportation options
      - Special assistance services
      - Accessible restroom locations

   c) Family Services:
      - Baby changing facilities
      - Family rest areas
      - Child-friendly attractions
      - Kids' meal options
      - Stroller rental services

   d) Emergency Services:
      - Hospital locations and specialties
      - 24-hour pharmacies
      - Police stations
      - Embassy/consulate details
      - Tourist police contacts
    """

    # Add religious facilities section if halal food is required
    if form.halal_food.data:
        religious_section = """
   e) Religious Facilities:
      - Nearby mosques and prayer rooms
      - Daily prayer times:
        * Fajr
        * Dhuhr
        * Asr
        * Maghrib
        * Isha
      - Walking distance to prayer facilities
      - Halal restaurants and certification details
      - Qibla direction in accommodation
      - Wudhu facilities availability
      - Friday prayer recommendations
      - Religious etiquette guidelines
      - Local Islamic cultural considerations
    """
        section += religious_section

    return section

def build_daily_schedule_structure(form):
    """Build the daily schedule structure with exact timings"""
    duration = (form.end_date.data - form.start_date.data).days + 1
    schedule = "\n5. Daily Schedule Structure:\n"

    # Build schedule for each day
    current_date = form.start_date.data
    for day in range(duration):
        day_date = current_date + timedelta(days=day)
        schedule += f"""
Day {day + 1} - {day_date.strftime('%A, %Y-%m-%d')}:

a) Early Morning (06:00-09:00):
   * [Time Slot Details]
   * Exact timing for each activity
   * Google Maps links
   * Transportation options
   * Weather considerations
   {'* Prayer facilities for Fajr' if form.halal_food.data else ''}

b) Morning Activities (09:00-12:00):
   * [Time Slot Details]
   * Location-specific information
   * Access requirements
   * Cost breakdown
   {'* Prayer facilities for Dhuhr' if form.halal_food.data else ''}

c) Afternoon Activities (12:00-17:00):
   * [Time Slot Details]
   * Rest periods
   * Meal recommendations
   * Indoor/outdoor alternatives
   {'* Prayer facilities for Dhuhr and Asr' if form.halal_food.data else ''}

d) Evening Activities (17:00-22:00):
   * [Time Slot Details]
   * Dinner options
   * Entertainment choices
   * Night activity suggestions
   {'* Prayer facilities for Maghrib and Isha' if form.halal_food.data else ''}

Required for each location:
1. [Location Name](https://www.google.com/maps/search/?api=1&query=encoded_location_name)
2. Opening hours and optimal visit time
3. Exact costs in {form.currency.data}
4. Travel duration from previous location
5. Public transport options
6. Accessibility information
7. Weather contingency plans
"""

    return schedule

def assemble_final_prompt(form):
    """Assemble all prompt sections into final prompt"""
    # Build base prompt
    prompt = build_detailed_prompt(form)

    # Add price breakdown
    prompt += build_price_breakdown_section(form)

    # Add requirements and cultural info
    prompt += build_requirements_section(form)

    # Add religious and accessibility features
    prompt += build_religious_accessibility_section(form)

    # Add daily schedule structure
    prompt += build_daily_schedule_structure(form)

    # Add final instructions
    prompt += f"""

Additional Requirements:
1. Timing:
   - Provide exact timings for all activities
   - Include travel duration between locations
   - Factor in prayer times where applicable
   - Consider peak hours and crowds
   - Include buffer time for unexpected delays

2. Location Details:
   - Google Maps links for all locations
   - Exact addresses
   - Best entry/exit points
   - Nearest public transport
   - Parking information if relevant

3. Cost Information:
   - All prices in {form.currency.data}
   - Include all taxes and fees
   - List both budget and premium options
   - Group discount opportunities
   - Hidden costs to consider

4. Weather Considerations:
   - Indoor alternatives for outdoor activities
   - Season-specific recommendations
   - Weather-dependent timing adjustments
   - Appropriate clothing suggestions

Please ensure all recommendations consider:
- Group composition and age ranges
- Selected travel focus areas
- Dietary requirements
- Accessibility needs
- Budget constraints
- Cultural sensitivities
"""

    return prompt

def get_prayer_times(date, location):
    """Helper function to get prayer times for a specific date and location"""
    # TODO: Implement prayer times API integration
    pass

def format_google_maps_link(location_name):
    """Helper function to properly format Google Maps links"""
    encoded_name = urllib.parse.quote(location_name)
    return f"https://www.google.com/maps/search/?api=1&query={encoded_name}"

def calculate_travel_duration(origin, destination, mode='driving'):
    """Helper function to calculate travel duration between locations"""
    # TODO: Implement Google Maps Distance Matrix API integration
    pass

def generate_itinerary(form):
    """Generate a complete travel itinerary using the appropriate GPT model with caching."""
    try:
        # Prepare request data for caching
        request_data = prepare_cache_data(form)

        # Try to get cached response
        cached_response = cache_manager.get_openai_response(request_data)
        if cached_response:
            logger.info("Using cached OpenAI response")
            return cached_response

        # Build system prompt
        system_prompt = build_system_prompt(form)

        # Assemble final detailed prompt
        user_prompt = assemble_final_prompt(form)

        # Get the appropriate model based on subscription
        logger.info(f"Using model {current_user.gpt_model_access} for user {current_user.id}")

        # Generate itinerary
        itinerary = GPTModelHandler.generate_itinerary(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7
        )

        # Cache the response
        cache_manager.cache_openai_response(request_data, itinerary)

        # Post-process the itinerary
        processed_itinerary = post_process_itinerary(itinerary, form)

        return processed_itinerary

    except Exception as e:
        logger.error(f"Error generating itinerary: {str(e)}")
        error_message = f"""
        We apologize, but we encountered an error while generating your itinerary. 
        Error Details: {str(e)}

        This could be due to:
        - Temporary service unavailability
        - Invalid input parameters
        - Network connectivity issues

        Your subscription tier: {current_user.subscription_tier}
        Model access level: {current_user.gpt_model_access}

        Please try again in a few moments. If the problem persists, contact support.
        """
        raise Exception(error_message)

def post_process_itinerary(itinerary, form):
    """Post-process the generated itinerary for final formatting and verification"""
    try:
        # Ensure all Google Maps links are properly formatted
        itinerary = fix_google_maps_links(itinerary)

        # Format all prices in the correct currency
        itinerary = format_currency_amounts(itinerary, form.currency.data)

        # Add prayer times if required
        if form.halal_food.data:
            itinerary = add_prayer_times(itinerary, form)

        # Verify all locations are accessible if required
        if form.wheelchair_accessible.data:
            itinerary = verify_accessibility(itinerary)

        return itinerary

    except Exception as e:
        logger.error(f"Error in post-processing: {str(e)}")
        return itinerary  # Return original if post-processing fails