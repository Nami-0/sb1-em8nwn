from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
import json
import os
import logging
import redis
from redis import Redis, RedisError
import requests
from decimal import Decimal
from datetime import datetime
from functools import wraps

from models import User, Itinerary, AccessViolation
from forms import ItineraryForm, ProfileForm
from extensions import db
from itinerary_generator import generate_itinerary, is_openai_available
from destination_validation import validate_budget_and_duration
from gpt_model_handler import GPTModelHandler
from currency_data import get_currency_info, format_currency
from cache_manager import CacheManager
from currency_routes import get_redis

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize cache manager
cache_manager = CacheManager()

main_views = Blueprint('main_views', __name__)

def check_subscription_limits(f):
    """Decorator to check subscription limits before processing requests"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('google_auth.login'))

        # Check if subscription is active
        if current_user.subscription_status != 'active':
            flash('Your subscription is not active. Please update your subscription.', 'warning')
            return redirect(url_for('main_views.pricing'))

        # Check if subscription has expired
        if current_user.subscription_end_date and current_user.subscription_end_date < datetime.utcnow():
            flash('Your subscription has expired. Please renew your subscription.', 'warning')
            return redirect(url_for('main_views.pricing'))

        return f(*args, **kwargs)
    return decorated_function

def update_exchange_rates():
    """Daily update of exchange rates from exchangerate-api"""
    try:
        if not cache_manager.needs_rate_update():
            logger.info("Exchange rates are up to date")
            return

        # Fetch new rates
        api_key = os.environ.get('EXCHANGERATE_API_KEY')
        response = requests.get(f'https://v6.exchangerate-api.com/v6/{api_key}/latest/MYR')

        if response.status_code == 200:
            rates = response.json().get('conversion_rates', {})
            # Store in Redis for 24 hours
            cache_manager.set_currency_rates(rates)
            logger.info("Successfully updated exchange rates")
        else:
            logger.error(f"Failed to fetch exchange rates: {response.status_code}")

    except Exception as e:
        logger.error(f"Error updating exchange rates: {str(e)}")

@main_views.context_processor
def inject_stripe_key():
    """Inject Stripe public key into all templates"""
    stripe_key = os.getenv('STRIPE_PUBLIC_KEY', '')
    if not stripe_key:
        logger.warning("STRIPE_PUBLIC_KEY not found in environment variables")

    return {'stripe_public_key': stripe_key}

@main_views.route('/admin/diagnostic')
@login_required
def diagnostic():
    try:
        if not current_user.is_admin:
            # Log unauthorized access attempt
            violation = AccessViolation(
                user_id=current_user.id,
                violation_type='unauthorized_admin_access',
                details='Attempted to access admin diagnostic page'
            )
            db.session.add(violation)
            db.session.commit()
            flash('Unauthorized access', 'danger')
            return redirect(url_for('main_views.index'))

        usage_stats = User.get_usage_stats()
        violations = AccessViolation.get_recent_violations()
        return render_template('admin/diagnostic.html',
                            usage_stats=usage_stats,
                            violations=violations)
    except Exception as e:
        logger.error(f"Error in diagnostic view: {str(e)}")
        flash('Error loading diagnostic data', 'danger')
        return redirect(url_for('main_views.index'))

@main_views.route('/pricing')
def pricing():
    """Render the pricing page with plan information"""
    try:
        # Get the billing cycle from query params, default to monthly
        billing_cycle = request.args.get('billing_cycle', 'monthly')
        if billing_cycle not in ['monthly', 'yearly']:
            billing_cycle = 'monthly'

        # Get current user's subscription details if logged in
        subscription_data = None
        if current_user.is_authenticated:
            subscription_data = {
                'current_tier': current_user.subscription_tier,
                'status': current_user.subscription_status,
                'end_date': current_user.subscription_end_date,
                'usage_percentage': current_user.usage_percentage,
                'remaining_itineraries': (
                    current_user.max_itineraries_per_month - 
                    current_user.itineraries_generated_this_month
                )
            }

        return render_template(
            'pricing.html',
            billing_cycle=billing_cycle,
            subscription=subscription_data,
            stripe_public_key=os.getenv('STRIPE_PUBLIC_KEY', ''),
            has_payment_method=bool(current_user.stripe_customer_id if current_user.is_authenticated else False)
        )

    except Exception as e:
        logger.error(f"Error rendering pricing page: {str(e)}")
        flash('Error loading pricing information. Please try again.', 'danger')
        return redirect(url_for('main_views.index'))

# Add these new routes right here
@main_views.route('/subscription/cancel', methods=['POST'])
@login_required
def cancel_subscription():
    """Handle subscription cancellation"""
    try:
        # Update user's subscription status
        current_user.subscription_status = 'cancelled'
        current_user.subscription_tier = 'solo_backpacker'
        db.session.commit()

        logger.info(f"Successfully cancelled subscription for user {current_user.id}")
        flash('Your subscription has been cancelled successfully.', 'success')
        return redirect(url_for('main_views.profile'))

    except Exception as e:
        logger.error(f"Error cancelling subscription: {str(e)}")
        db.session.rollback()
        flash('Failed to cancel subscription. Please try again.', 'danger')
        return redirect(url_for('main_views.profile'))

@main_views.route('/subscription/status', methods=['GET'])
@login_required
def subscription_status():
    """Get current subscription status"""
    return jsonify({
        'status': current_user.subscription_status,
        'tier': current_user.subscription_tier,
        'end_date': current_user.subscription_end_date.isoformat() if current_user.subscription_end_date else None
    })

@main_views.route('/subscription/upgrade', methods=['POST'])
@login_required
def upgrade_subscription():
    """Handle subscription upgrade"""
    try:
        tier = request.form.get('tier')
        if tier not in ['tandem_trekker', 'gold_wanderer', 'business']:
            flash('Invalid subscription tier selected.', 'danger')
            return redirect(url_for('main_views.pricing'))

        # Update user's subscription
        current_user.subscription_tier = tier
        current_user.subscription_status = 'active'
        db.session.commit()

        logger.info(f"Successfully upgraded subscription for user {current_user.id} to {tier}")
        flash(f'Successfully upgraded to {tier.replace("_", " ").title()}!', 'success')
        return redirect(url_for('main_views.profile'))

    except Exception as e:
        logger.error(f"Error upgrading subscription: {str(e)}")
        db.session.rollback()
        flash('Failed to upgrade subscription. Please try again.', 'danger')
        return redirect(url_for('main_views.pricing'))

@main_views.route('/subscription/cancel', methods=['POST'])
@login_required
def cancel_subscription():
    """Handle subscription cancellation"""
    try:
        # Update user's subscription status
        current_user.subscription_status = 'cancelled'
        current_user.subscription_tier = 'solo_backpacker'

        db.session.commit()

        logger.info(f"Successfully cancelled subscription for user {current_user.id}")
        flash('Your subscription has been cancelled successfully.', 'success')
        return redirect(url_for('main_views.profile'))

    except Exception as e:
        logger.error(f"Error cancelling subscription: {str(e)}")
        db.session.rollback()
        flash('Failed to cancel subscription. Please try again.', 'danger')
        return redirect(url_for('main_views.profile'))

@main_views.route('/subscription/status', methods=['GET'])
@login_required
def subscription_status():
    """Get current subscription status"""
    return jsonify({
        'status': current_user.subscription_status,
        'tier': current_user.subscription_tier,
        'end_date': current_user.subscription_end_date.isoformat() if current_user.subscription_end_date else None
    })

@main_views.route('/subscription/upgrade', methods=['POST'])
@login_required
def upgrade_subscription():
    """Handle subscription upgrade"""
    try:
        tier = request.form.get('tier')
        if tier not in ['tandem_trekker', 'gold_wanderer', 'business']:
            flash('Invalid subscription tier selected.', 'danger')
            return redirect(url_for('main_views.pricing'))

        # Update user's subscription
        current_user.subscription_tier = tier
        current_user.subscription_status = 'active'
        db.session.commit()

        logger.info(f"Successfully upgraded subscription for user {current_user.id} to {tier}")
        flash(f'Successfully upgraded to {tier.replace("_", " ").title()}!', 'success')
        return redirect(url_for('main_views.profile'))

    except Exception as e:
        logger.error(f"Error upgrading subscription: {str(e)}")
        db.session.rollback()
        flash('Failed to upgrade subscription. Please try again.', 'danger')
        return redirect(url_for('main_views.pricing'))

@main_views.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()
    if request.method == 'GET':
        form.username.data = current_user.username
        form.phone_number.data = current_user.phone_number
        form.preferred_currency.data = current_user.preferred_currency

    if form.validate_on_submit():
        try:
            existing_user = User.query.filter(
                User.phone_number == form.phone_number.data,
                User.id != current_user.id
            ).first()

            if existing_user:
                flash('This phone number is already registered to another account.', 'danger')
                return render_template('profile.html', form=form)

            current_user.username = form.username.data
            current_user.phone_number = form.phone_number.data
            current_user.preferred_currency = form.preferred_currency.data

            logger.info(f"Updating profile for user {current_user.id}")
            db.session.commit()
            logger.info(f"Successfully updated profile for user {current_user.id}")

            flash('Profile updated successfully!', 'success')
            return redirect(url_for('main_views.profile'))

        except Exception as e:
            logger.error(f"Error updating profile: {str(e)}")
            db.session.rollback()
            flash('An error occurred while updating your profile.', 'danger')

    model_features = GPTModelHandler.get_model_features(current_user.subscription_tier)
    return render_template('profile.html', 
                         form=form, 
                         model_features=model_features)


@main_views.route('/itinerary', methods=['GET', 'POST'])
@login_required
@check_subscription_limits
def itinerary_form():
    try:
        # Initial phone number check
        if not current_user.phone_number:
            flash('Please add your phone number to your profile before creating an itinerary.', 'warning')
            return redirect(url_for('main_views.profile'))

        # Check rate limiting from cache
        cache_key = f"rate_limit:user:{current_user.id}"
        if cache_manager.exists(cache_key):
            flash('Please wait a moment before generating another itinerary.', 'warning')
            return redirect(url_for('main_views.index'))

        # Monthly limit check with violation tracking
        if current_user.itineraries_generated_this_month >= current_user.max_itineraries_per_month:
            violation = AccessViolation(
                user_id=current_user.id,
                violation_type='monthly_limit_exceeded',
                details=f'Attempted to exceed monthly limit of {current_user.max_itineraries_per_month} itineraries'
            )
            db.session.add(violation)
            db.session.commit()

            flash(f'You have reached your monthly limit of {current_user.max_itineraries_per_month} itineraries. Please upgrade your plan to create more.', 'warning')
            return redirect(url_for('main_views.pricing'))

        form = ItineraryForm()

        # Set default currency from user preferences
        if request.method == 'GET':
            form.currency.data = current_user.preferred_currency

        openai_api_available = is_openai_available()

        if form.validate_on_submit():
            # Update exchange rates if needed
            update_exchange_rates()

            total_travelers = (
                form.num_adults.data +
                form.num_youth.data +
                form.num_children.data
            )
            num_infants = form.num_infants.data

            # Validate against plan limits with violation tracking
            if total_travelers > current_user.max_travelers:
                violation = AccessViolation(
                    user_id=current_user.id,
                    violation_type='max_travelers_exceeded',
                    details=f'Attempted to create itinerary for {total_travelers} travelers (limit: {current_user.max_travelers})'
                )
                db.session.add(violation)
                db.session.commit()

                flash(f'Your current plan allows a maximum of {current_user.max_travelers} travelers. Please upgrade your plan for larger groups.', 'warning')
                return redirect(url_for('main_views.pricing'))

            # Validate infants limit
            if num_infants > current_user.max_infants:
                flash(f'Your current plan allows a maximum of {current_user.max_infants} infants.', 'warning')
                return render_template('itinerary_form.html', form=form, 
                                    openai_api_available=openai_api_available)

            # Validate trip duration
            trip_duration = (form.end_date.data - form.start_date.data).days + 1
            if trip_duration > current_user.max_duration:
                violation = AccessViolation(
                    user_id=current_user.id,
                    violation_type='max_duration_exceeded',
                    details=f'Attempted to create {trip_duration}-day itinerary (limit: {current_user.max_duration} days)'
                )
                db.session.add(violation)
                db.session.commit()

                flash(f'Your current plan allows a maximum trip duration of {current_user.max_duration} days. Please upgrade your plan for longer trips.', 'warning')
                return redirect(url_for('main_views.pricing'))

            # Validate budget and duration
            is_valid, messages = validate_budget_and_duration(
                form.destinations.data,
                form.budget.data,
                total_travelers,
                form.start_date.data,
                form.end_date.data,
                form.include_flights.data,
                form.include_accommodation.data,
                form.need_guide.data
            )

            if not is_valid:
                for message in messages:
                    flash(message, 'warning')
                return render_template('itinerary_form.html', form=form,
                                    openai_api_available=openai_api_available)

            # Check OpenAI availability
            if not openai_api_available:
                flash('Cannot generate itinerary at this time. The service is temporarily unavailable.', 'danger')
                return redirect(url_for('main_views.itinerary_form'))

            try:
                # Set rate limiting in cache
                cache_manager.set(cache_key, 1, timeout=30)  # 30 seconds cooldown

                # Generate itinerary content
                content = generate_itinerary(form)

                # Create itinerary object
                itinerary = Itinerary(
                    user_id=current_user.id,
                    destination=form.destinations.data,
                    specific_locations=form.specific_locations.data,
                    travel_focus=form.travel_focus.data,
                    budget=form.budget.data,
                    currency=form.currency.data,
                    include_flights=form.include_flights.data,
                    include_accommodation=form.include_accommodation.data,
                    num_adults=form.num_adults.data,
                    num_youth=form.num_youth.data,
                    num_children=form.num_children.data,
                    num_infants=form.num_infants.data,
                    accommodation_location=form.accommodation_location.data,
                    accommodation_name=form.accommodation_name.data,
                    need_guide=form.need_guide.data,
                    halal_food=form.halal_food.data,
                    vegan_food=form.vegan_food.data,
                    start_date=form.start_date.data,
                    end_date=form.end_date.data,
                    content=content,
                    citizenship=form.citizenship.data
                )

                logger.info(f"Creating new itinerary for user {current_user.id}")
                db.session.add(itinerary)

                # Update user's monthly usage
                current_user.itineraries_generated_this_month += 1
                if not current_user.last_reset_date:
                    current_user.last_reset_date = datetime.utcnow()

                db.session.commit()
                logger.info(f"Successfully created itinerary {itinerary.id}")

                # Track GPT model usage for analytics
                model_used = GPTModelHandler.get_model_for_user()
                logger.info(f"Generated itinerary using {model_used} for user {current_user.id}")

                return render_template('itinerary_result.html', 
                                    itinerary=itinerary,
                                    currency_info=get_currency_info(itinerary.currency))

            except Exception as e:
                logger.error(f"Error generating itinerary: {str(e)}", exc_info=True)
                db.session.rollback()
                flash('Error generating itinerary. Please try again.', 'danger')
                return redirect(url_for('main_views.itinerary_form'))

        # Pass the user's plan limits to the template
        return render_template(
            'itinerary_form.html',
            form=form,
            openai_api_available=openai_api_available,
            max_duration=current_user.max_duration,
            max_travelers=current_user.max_travelers,
            max_infants=current_user.max_infants,
            remaining_itineraries=current_user.max_itineraries_per_month - current_user.itineraries_generated_this_month,
            gpt_model=GPTModelHandler.get_model_for_user()
        )

    except Exception as e:
        logger.error(f"Error in itinerary form: {str(e)}", exc_info=True)
        flash('An unexpected error occurred. Please try again.', 'danger')
        return redirect(url_for('main_views.index'))

@main_views.route('/about')
def about():
    return render_template('about.html')

@main_views.route('/how-it-works')
def how_it_works():
    return render_template('how_it_works.html')

@main_views.route('/flights')
def flights():
    return render_template('flights.html')

@main_views.route('/accommodations')
def accommodations():
    return render_template('accommodations.html')

@main_views.route('/news')
def news():
    return render_template('news.html')

@main_views.route('/disclaimer')
def disclaimer():
    return render_template('disclaimer.html', current_year=datetime.now().year)

@main_views.route('/terms')
def terms():
    return render_template('terms.html', current_year=datetime.now().year)

@main_views.route('/privacy')
def privacy():
    return render_template('privacy.html', current_year=datetime.now().year)

@main_views.route('/contact')
def contact():
    return render_template('contact.html', current_year=datetime.now().year)

@main_views.route('/faq')
def faq():
    return render_template('faq.html', current_year=datetime.now().year)

@main_views.route('/')
def index():
    """Homepage route"""
    try:
        return render_template(
            'index.html',
            current_year=datetime.now().year,
            user=current_user if not current_user.is_anonymous else None
        )
    except Exception as e:
        logger.error(f"Error rendering index: {str(e)}", exc_info=True)
        # Fallback to a simple response if template rendering fails
        return "Welcome to Travel Buddy. We're experiencing technical difficulties. Please try again later."

# Error handlers
@main_views.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@main_views.errorhandler(500)
def internal_error(error):
    db.session.rollback()  # Reset any failed database sessions
    return render_template('errors/500.html'), 500

@main_views.errorhandler(403)
def forbidden_error(error):
    return render_template('errors/403.html'), 403

@main_views.errorhandler(redis.RedisError)
def handle_redis_error(error):
    logger.error(f"Redis error: {str(error)}")
    # Continue with filesystem session
    return None

# API endpoints for dynamic updates
@main_views.route('/api/user/usage', methods=['GET'])
@login_required
def get_user_usage():
    """Get user's current usage statistics"""
    try:
        return jsonify({
            'itineraries_used': current_user.itineraries_generated_this_month,
            'itineraries_total': current_user.max_itineraries_per_month,
            'days_until_reset': current_user.days_until_reset,
            'usage_percentage': current_user.usage_percentage
        })
    except Exception as e:
        logger.error(f"Error getting user usage: {str(e)}")
        return jsonify({'error': 'Failed to get usage data'}), 500

@main_views.route('/api/subscription/check', methods=['GET'])
@login_required
def check_subscription():
    """Check subscription status and limits"""
    try:
        return jsonify({
            'status': current_user.subscription_status,
            'tier': current_user.subscription_tier,
            'max_travelers': current_user.max_travelers,
            'max_duration': current_user.max_duration,
            'max_itineraries': current_user.max_itineraries_per_month,
            'has_advanced_ai': current_user.has_advanced_ai
        })
    except Exception as e:
        logger.error(f"Error checking subscription: {str(e)}")
        return jsonify({'error': 'Failed to check subscription status'}), 500

# Health check endpoint
@main_views.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check database connection
        db.session.execute('SELECT 1')

        # Check Redis if available
        cache_status = cache_manager.get_status()

        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'cache': 'connected' if cache_status else 'fallback',
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 503