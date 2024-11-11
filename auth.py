from flask import Blueprint, redirect, url_for, session, request, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
import os
from models import User
from extensions import db
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse
import redis

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

google_auth = Blueprint('google_auth', __name__)

# OAuth2 configuration
CLIENT_SECRETS_FILE = {
    "web": {
        "client_id": os.getenv('GOOGLE_OAUTH_CLIENT_ID'),
        "client_secret": os.getenv('GOOGLE_OAUTH_CLIENT_SECRET'),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": []  # Will be set dynamically
    }
}

SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']

def is_development():
    """Check if running in development environment"""
    return (
        'REPLIT_ENVIRONMENT' in os.environ or
        'GITPOD_WORKSPACE_ID' in os.environ or
        'CODESPACE_NAME' in os.environ or
        current_app.debug
    )

def get_redirect_uri():
    """
    Get the dynamic redirect URI handling both Replit and Cloudflare URLs.
    """
    try:
        # Handle development environments
        if is_development():
            # Allow HTTP in development
            os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
            proto = request.scheme
            host = request.host
            callback_path = url_for('google_auth.oauth2callback', _external=False)
            redirect_uri = f"{proto}://{host}{callback_path}"
            logger.info(f"Using development URI: {redirect_uri}")
            return redirect_uri

        # For production with Cloudflare
        proto = 'https'
        callback_path = url_for('google_auth.oauth2callback', _external=True)
        redirect_uri = callback_path
        logger.info(f"Using production URI: {redirect_uri}")
        return redirect_uri

    except Exception as e:
        logger.error(f"Error generating redirect URI: {str(e)}")
        raise

@google_auth.route('/login')
def login():
    """Initiate Google OAuth login"""
    try:
        # Store the next URL in session if provided
        if 'next' in request.args:
            session['next'] = request.args.get('next')

        logger.debug("Starting login process")
        logger.debug(f"Request headers: {dict(request.headers)}")
        logger.debug(f"Request URL: {request.url}")

        # Validate OAuth credentials
        if not os.getenv('GOOGLE_OAUTH_CLIENT_ID') or not os.getenv('GOOGLE_OAUTH_CLIENT_SECRET'):
            logger.error("Google OAuth credentials not configured")
            flash('Authentication service is not properly configured.', 'danger')
            return redirect(url_for('main_views.index'))

        # Get redirect URI and update config
        redirect_uri = get_redirect_uri()
        CLIENT_SECRETS_FILE["web"]["redirect_uris"] = [redirect_uri]
        logger.debug(f"Updated redirect URIs: {CLIENT_SECRETS_FILE['web']['redirect_uris']}")

        # Create OAuth flow
        try:
            flow = google_auth_oauthlib.flow.Flow.from_client_config(
                CLIENT_SECRETS_FILE,
                scopes=SCOPES
            )
            flow.redirect_uri = redirect_uri
            logger.debug(f"Created OAuth flow with redirect URI: {redirect_uri}")
        except Exception as e:
            logger.error(f"Failed to create OAuth flow: {str(e)}", exc_info=True)
            flash('Failed to initialize authentication. Please try again.', 'danger')
            return redirect(url_for('main_views.index'))

        # Generate authorization URL
        try:
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            session['state'] = state
            logger.info(f"Generated authorization URL: {authorization_url}")
            return redirect(authorization_url)
        except Exception as e:
            logger.error(f"Failed to generate authorization URL: {str(e)}", exc_info=True)
            flash('Authentication initialization failed. Please try again.', 'danger')
            return redirect(url_for('main_views.index'))

    except Exception as e:
        logger.error(f"Error in login route: {str(e)}", exc_info=True)
        flash('An error occurred during login. Please try again.', 'danger')
        return redirect(url_for('main_views.index'))

@google_auth.route('/google_login/callback')
def oauth2callback():
    """Handle Google OAuth callback"""
    try:
        logger.debug(f"Callback received with URL: {request.url}")
        logger.debug(f"State in session: {session.get('state')}")

        # Verify state
        state = session.get('state')
        if not state:
            logger.error("State not found in session")
            flash('Invalid session state. Please try logging in again.', 'danger')
            return redirect(url_for('main_views.index'))

        # Get redirect URI and update config
        redirect_uri = get_redirect_uri()
        CLIENT_SECRETS_FILE["web"]["redirect_uris"] = [redirect_uri]
        logger.debug(f"Callback - Using redirect URI: {redirect_uri}")

        # Create flow
        try:
            flow = google_auth_oauthlib.flow.Flow.from_client_config(
                CLIENT_SECRETS_FILE,
                scopes=SCOPES,
                state=state
            )
            flow.redirect_uri = redirect_uri
            logger.debug("Successfully created OAuth flow in callback")
        except Exception as e:
            logger.error(f"Failed to create OAuth flow in callback: {str(e)}")
            flash('Authentication process failed. Please try again.', 'danger')
            return redirect(url_for('main_views.index'))

        # Handle OAuth error parameters
        if 'error' in request.args:
            error = request.args.get('error')
            logger.error(f"OAuth error: {error}")
            flash('Authentication failed. Please try again.', 'danger')
            return redirect(url_for('main_views.index'))

        # Exchange authorization code for tokens
        try:
            flow.fetch_token(authorization_response=request.url)
            logger.debug("Successfully fetched OAuth token")
        except Exception as e:
            logger.error(f"Failed to fetch OAuth token: {str(e)}")
            flash('Failed to authenticate with Google. Please try again.', 'danger')
            return redirect(url_for('main_views.index'))

        # Get user info
        try:
            oauth2_client = googleapiclient.discovery.build('oauth2', 'v2', credentials=flow.credentials)
            user_info = oauth2_client.userinfo().get().execute()
            logger.debug("Successfully retrieved user info from Google")
            logger.debug(f"User info: {user_info}")
        except Exception as e:
            logger.error(f"Failed to fetch user info: {str(e)}")
            flash('Failed to retrieve user information. Please try again.', 'danger')
            return redirect(url_for('main_views.index'))

        # Process user info
        email = user_info.get('email')
        if not email:
            logger.error("No email received from Google")
            flash('Could not retrieve email from Google. Please try again.', 'danger')
            return redirect(url_for('main_views.index'))

        # Database operations
        try:
            # Create or update user
            with current_app.app_context():
                user = User.query.filter_by(email=email).first()

                if not user:
                    # Create new user
                    user = User(
                        email=email,
                        username=user_info.get('name'),
                        subscription_tier='solo_backpacker',
                        last_login=datetime.utcnow()
                    )
                    db.session.add(user)
                    logger.info(f"Created new user: {email}")
                else:
                    # Update existing user
                    user.last_login = datetime.utcnow()
                    logger.info(f"Updated existing user: {email}")

                try:
                    db.session.commit()
                    login_user(user)
                    flash('Successfully logged in!', 'success')

                    next_url = session.get('next') or url_for('main_views.itinerary_form')
                    return redirect(next_url)

                except Exception as e:
                    logger.error(f"Database error during commit: {str(e)}", exc_info=True)
                    db.session.rollback()
                    flash('An error occurred while updating your account. Please try again.', 'danger')
                    return redirect(url_for('main_views.index'))

        except Exception as e:
            logger.error(f"Database error during user creation/login: {str(e)}", exc_info=True)
            db.session.rollback()
            flash('An error occurred while creating your account. Please try again.', 'danger')
            return redirect(url_for('main_views.index'))

    except redis.RedisError as e:
        logger.error(f"Redis error in callback: {str(e)}", exc_info=True)
        flash('Session error occurred. Please try again.', 'danger')
        return redirect(url_for('main_views.index'))

    except Exception as e:
        logger.error(f"Error in oauth2callback: {str(e)}", exc_info=True)
        flash('An error occurred during login. Please try again.', 'danger')
        return redirect(url_for('main_views.index'))

@google_auth.route('/logout')
@login_required
def logout():
    """Handle user logout"""
    try:
        logout_user()
        session.clear()
        logger.info("User logged out successfully")
        flash('Successfully logged out!', 'success')
    except Exception as e:
        logger.error(f"Error in logout: {str(e)}")
        flash('An error occurred during logout.', 'danger')
    return redirect(url_for('main_views.index'))