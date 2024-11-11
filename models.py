from datetime import datetime, timedelta
from flask_login import UserMixin
from extensions import db
from cache_manager import CacheManager, cache_enabled
from currency_data import get_default_currency, CURRENCY_DATA, format_currency
from decimal import Decimal

cache_manager = CacheManager()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(80))
    phone_number = db.Column(db.String(20), unique=True)
    subscription_tier = db.Column(db.String(20), default='solo_backpacker')
    itineraries_generated_this_month = db.Column(db.Integer, default=0)
    last_reset_date = db.Column(db.DateTime)
    is_admin = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)  # Added this field
    stripe_customer_id = db.Column(db.String(120), unique=True)
    subscription_status = db.Column(db.String(20), default='active')
    subscription_end_date = db.Column(db.DateTime)
    preferred_currency = db.Column(db.String(3), default='MYR')
    last_currency_update = db.Column(db.DateTime)
    last_login = db.Column(db.DateTime)  # Added this field


    @property
    def subscription_price(self):
        """Get subscription price in USD"""
        prices = {
            'solo_backpacker': 0,       # Free tier
            'tandem_trekker': 4.99,     # Basic paid tier
            'gold_wanderer': 14.99,     # Premium tier
            'business': None            # Custom pricing
        }
        return prices.get(self.subscription_tier)

    @property
    def max_itineraries_per_month(self):
        limits = {
            'solo_backpacker': 1,      # Free tier
            'tandem_trekker': 3,       # $4.99 tier
            'gold_wanderer': 6,        # $14.99 tier
            'business': float('inf')    # Business tier
        }
        return limits.get(self.subscription_tier, 1)

    @property
    def max_travelers(self):
        limits = {
            'solo_backpacker': 1,
            'tandem_trekker': 2,
            'gold_wanderer': 10,
            'business': 20
        }
        return limits.get(self.subscription_tier, 1)

    @property
    def max_infants(self):
        limits = {
            'solo_backpacker': 0,
            'tandem_trekker': 2,
            'gold_wanderer': 5,
            'business': 10
        }
        return limits.get(self.subscription_tier, 0)

    @property
    def max_duration(self):
        limits = {
            'solo_backpacker': 1,
            'tandem_trekker': 3,
            'gold_wanderer': 7,
            'business': 14
        }
        return limits.get(self.subscription_tier, 1)

    @property
    def has_advanced_ai(self):
        """Check if user has access to advanced AI features"""
        return self.subscription_tier in ['tandem_trekker', 'gold_wanderer', 'business']

    @property
    def gpt_model_access(self):
        """Get the GPT model access level for the user"""
        model_access = {
            'solo_backpacker': 'gpt-3.5-turbo',  # Free tier
            'tandem_trekker': 'gpt-4',           # Paid tiers get GPT-4
            'gold_wanderer': 'gpt-4',
            'business': 'gpt-4'
        }
        return model_access.get(self.subscription_tier, 'gpt-3.5-turbo')

    @property
    def has_priority_support(self):
        """Check if user has access to priority support"""
        return self.subscription_tier in ['gold_wanderer', 'business']

    @property
    def can_access_travel_buddy(self):
        """Check if user can access Travel Buddy feature"""
        return self.subscription_tier in ['gold_wanderer', 'business']

    @property
    def can_export_pdf(self):
        """Check if user can export to PDF"""
        return self.subscription_tier in ['gold_wanderer', 'business']

    def format_price(self, amount: Decimal) -> str:
        """Format price in user's preferred currency"""
        return format_currency(amount, self.preferred_currency)

    def update_currency_preference(self, currency_code: str) -> bool:
        """Update user's preferred currency"""
        if currency_code in CURRENCY_DATA:
            self.preferred_currency = currency_code
            self.last_currency_update = datetime.utcnow()
            return True
        return False

    @staticmethod
    def reset_monthly_usage():
        """Reset monthly usage counters for all users"""
        try:
            users = User.query.all()
            current_time = datetime.utcnow()
            for user in users:
                if user.last_reset_date:
                    # Calculate days since last reset
                    days_since_reset = (current_time - user.last_reset_date).days
                    if days_since_reset >= 30:  # Reset monthly counter
                        user.itineraries_generated_this_month = 0
                        user.last_reset_date = current_time
                else:
                    # Initialize reset date if not set
                    user.last_reset_date = current_time
            db.session.commit()
            logger.info("Successfully reset monthly usage counters")
        except Exception as e:
            logger.error(f"Error resetting monthly usage: {str(e)}")
            db.session.rollback()

    @property
    def days_until_reset(self):
        """Calculate days until next usage reset"""
        if not self.last_reset_date:
            return 0
        next_reset = self.last_reset_date + timedelta(days=30)
        days_remaining = (next_reset - datetime.utcnow()).days
        return max(0, days_remaining)

    @property
    def usage_percentage(self):
        """Calculate current usage percentage"""
        if self.max_itineraries_per_month == 0:
            return 0
        return (self.itineraries_generated_this_month / self.max_itineraries_per_month) * 100

    def get_stripe_price_id(self, interval='month'):
        """Get Stripe price ID based on tier and interval"""
        yearly_discount = 0.17  # 17% discount for yearly plans
        price_mapping = {
            'tandem_trekker': {
                'month': 'price_monthly_tandem_trekker',  # $4.99/month
                'year': 'price_yearly_tandem_trekker'     # $49.90/year (Save 17%)
            },
            'gold_wanderer': {
                'month': 'price_monthly_gold_wanderer',   # $14.99/month
                'year': 'price_yearly_gold_wanderer'      # $149.90/year (Save 17%)
            }
        }
        return price_mapping.get(self.subscription_tier, {}).get(interval)

    def calculate_usage_percentage(self):
        """Calculate current usage percentage"""
        if self.subscription_tier == 'business':
            return [0, "Unlimited"]
        max_itineraries = self.max_itineraries_per_month
        current = self.itineraries_generated_this_month
        percentage = (current / max_itineraries * 100) if max_itineraries > 0 else 0
        return [round(percentage, 1), f"{current}/{max_itineraries}"]

    @classmethod
    @cache_enabled
    def get_by_id(cls, user_id):
        """Get user by ID with caching"""
        cached_data = cache_manager.get_user_data(user_id)
        if cached_data:
            user = cls()
            for key, value in cached_data.items():
                setattr(user, key, value)
            return user

        user = cls.query.get(user_id)
        if user:
            cache_manager.cache_user_data(user_id, {
                'id': user.id,
                'email': user.email,
                'username': user.username,
                'phone_number': user.phone_number,
                'subscription_tier': user.subscription_tier,
                'itineraries_generated_this_month': user.itineraries_generated_this_month,
                'last_reset_date': user.last_reset_date.isoformat() if user.last_reset_date else None,
                'is_admin': user.is_admin,
                'stripe_customer_id': user.stripe_customer_id,
                'subscription_status': user.subscription_status,
                'subscription_end_date': user.subscription_end_date.isoformat() if user.subscription_end_date else None,
                'preferred_currency': user.preferred_currency
            })
        return user

    def save(self):
        """Save user and update cache"""
        db.session.add(self)
        db.session.commit()
        cache_manager.clear_user_cache(self.id)

    @staticmethod
    def get_usage_stats():
        """Get system-wide usage statistics"""
        stats = {
            'total_users': User.query.count(),
            'premium_users': User.query.filter(User.subscription_tier.in_(['tandem_trekker', 'gold_wanderer'])).count(),
            'business_users': User.query.filter_by(subscription_tier='business').count()
        }
        return stats

class Itinerary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    destination = db.Column(db.String(100), nullable=False)
    specific_locations = db.Column(db.String(500))
    travel_focus = db.Column(db.JSON, nullable=False)
    budget = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='MYR')  # New: Currency field
    include_flights = db.Column(db.Boolean, default=True)
    include_accommodation = db.Column(db.Boolean, default=True)
    num_adults = db.Column(db.Integer, nullable=False, default=1)
    num_youth = db.Column(db.Integer, nullable=False, default=0)
    num_children = db.Column(db.Integer, nullable=False, default=0)
    num_infants = db.Column(db.Integer, nullable=False, default=0)
    accommodation_location = db.Column(db.String(200))
    accommodation_name = db.Column(db.String(200))
    need_guide = db.Column(db.Boolean, default=False)
    halal_food = db.Column(db.Boolean, default=False)
    vegan_food = db.Column(db.Boolean, default=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    citizenship = db.Column(db.String(100), default='malaysia')

    def format_budget(self):
        """Format budget with proper currency"""
        return format_currency(Decimal(str(self.budget)), self.currency)

class AccessViolation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    violation_type = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text)

    user = db.relationship('User', backref='violations')

    @staticmethod
    def get_recent_violations(limit=10):
        """Get recent access violations"""
        try:
            violations = AccessViolation.query.order_by(
                AccessViolation.timestamp.desc()).limit(limit).all()

            return [{
                'timestamp': v.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'user_email': v.user.email,
                'subscription': v.user.subscription_tier.replace('_', ' ').title(),
                'type': v.violation_type,
                'details': v.details
            } for v in violations]

        except Exception as e:
            return []