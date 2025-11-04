from flask import Blueprint, request, jsonify, current_app, g
from ..database import db
from ..models import User, LoginAttempt, Session
from datetime import datetime, timedelta
from functools import wraps
import secrets
import re
import jwt
import os

auth_bp = Blueprint('auth', __name__)

# ============================================
# 🔧 TEMPORARY DEV MODE (REMOVE IN PRODUCTION)
# ============================================
DEV_MODE = os.getenv('DEV_MODE', 'true').lower() == 'true'  # Set to 'false' in production

# --- Configuration and Helpers ---

def get_client_ip():
    """Get client IP address"""
    if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        return request.environ['REMOTE_ADDR']
    else:
        return request.environ['HTTP_X_FORWARDED_FOR']

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Validate password strength"""
    # ⚠️ RELAXED FOR DEV MODE
    if DEV_MODE and len(password) >= 4:
        return True, "Password is valid (dev mode)"
    
    # Production validation
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    return True, "Password is valid"

def check_rate_limit(email, max_attempts=5, window_minutes=15):
    """Check if user has exceeded login attempts"""
    # ⚠️ DISABLED IN DEV MODE
    if DEV_MODE:
        return True
    
    cutoff_time = datetime.utcnow() - timedelta(minutes=window_minutes)
    
    recent_attempts = LoginAttempt.query.filter(
        LoginAttempt.email == email,
        LoginAttempt.attempted_at > cutoff_time,
        LoginAttempt.success == False
    ).count()
    
    return recent_attempts < max_attempts

def log_login_attempt(email, ip_address, success):
    """Log login attempt"""
    try:
        attempt = LoginAttempt(
            email=email,
            ip_address=ip_address,
            success=success
        )
        session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.add(attempt)
    except Exception as e:
        print(f"Warning: Could not log login attempt: {e}")

# --- Decorators ---

def token_required(f):
    """Decorator to require valid JWT token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # ⚠️ DEV MODE: Accept any token or no token
        if DEV_MODE:
            # Try to get user from token if provided, otherwise use mock user
            token = None
            if 'Authorization' in request.headers:
                try:
                    token = request.headers['Authorization'].split(" ")[1]
                    if token == 'mock-jwt-token-123':
                        # Mock user for testing
                        mock_user = User.query.first()
                        if mock_user:
                            g.user = mock_user
                        else:
                            # Create a mock user object if no users exist
                            g.user = type('User', (), {
                                'id': 1,
                                'email': 'dev@test.com',
                                'first_name': 'Dev',
                                'last_name': 'User',
                                'role': 'Manager',
                                'is_active': True,
                                'to_dict': lambda: {
                                    'id': 1,
                                    'email': 'dev@test.com',
                                    'first_name': 'Dev',
                                    'last_name': 'User',
                                    'role': 'Manager'
                                }
                            })()
                        return f(*args, **kwargs)
                except:
                    pass
            
            # If no valid token, try to get first user from DB
            user = User.query.first()
            if user:
                g.user = user
                return f(*args, **kwargs)
            
            # Last resort: create mock user
            g.user = type('User', (), {
                'id': 1,
                'email': 'dev@test.com',
                'first_name': 'Dev',
                'last_name': 'User',
                'role': 'Manager',
                'is_active': True,
                'to_dict': lambda: {
                    'id': 1,
                    'email': 'dev@test.com',
                    'first_name': 'Dev',
                    'last_name': 'User',
                    'role': 'Manager'
                }
            })()
            return f(*args, **kwargs)
        
        # PRODUCTION MODE: Full JWT validation
        token = None
        if 'Authorization' in request.headers:
            try:
                token = request.headers['Authorization'].split(" ")[1]
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401

        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        try:
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            user = User.query.get(payload['user_id'])
            if not user or not user.is_active:
                return jsonify({'error': 'User not found or inactive'}), 401

            session = Session.query.filter_by(session_token=token, user_id=user.id).first()
            if not session or session.expires_at < datetime.utcnow():
                return jsonify({'error': 'Token expired'}), 401

            g.user = user

        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    """Decorator to require high-level access"""
    @wraps(f)
    @token_required
    def decorated(*args, **kwargs):
        # ⚠️ DEV MODE: Allow all
        if DEV_MODE:
            return f(*args, **kwargs)
        
        # PRODUCTION MODE: Check roles
        ADMIN_ROLES = ['Manager', 'HR'] 
        if g.user.role not in ADMIN_ROLES:
            return jsonify({'error': 'Manager or HR access required'}), 403
        return f(*args, **kwargs)
    return decorated

# --- Routes ---

@auth_bp.route('/health', methods=['GET'])
def health_check():
    mode = "🔧 DEV MODE (No Auth)" if DEV_MODE else "🔒 PRODUCTION MODE (Full Auth)"
    return {
        'status': 'ok', 
        'message': 'Backend is running successfully!',
        'mode': mode
    }, 200

@auth_bp.route('/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json() or {}

        # Validate required fields
        required_fields = ['email', 'password', 'first_name', 'last_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400

        email = data['email'].lower().strip()
        password = data['password']
        first_name = data['first_name'].strip()
        last_name = data['last_name'].strip()
        role = data.get('role', 'Staff').strip()  # Default to Staff

        # Validate email format
        if not validate_email(email):
            return jsonify({'error': 'Invalid email format'}), 400

        # Validate password strength
        is_valid, message = validate_password(password)
        if not is_valid:
            return jsonify({'error': message}), 400

        # Validate role against allowed values (relaxed in dev mode)
        ALLOWED_ROLES = ['Manager', 'HR', 'Sales', 'Production', 'Staff'] 
        if role not in ALLOWED_ROLES:
            role = 'Staff'  # Default to Staff if invalid

        # Check if user already exists
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already registered'}), 409

        # Create new user 
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            is_active=True,
            is_verified=True  # Auto-verify in dev mode
        )
        user.set_password(password)
        
        if not DEV_MODE:
            user.generate_verification_token()

        session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.add(user)
        
        # Log attempt
        log_login_attempt(email, get_client_ip(), True)
        
        session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.commit()

        print(f"✅ User registered: {email} as {role}")

        return jsonify({
            'success': True,
            'message': 'User registered successfully',
            'user': user.to_dict()
        }), 201

    except Exception as e:
        session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.rollback()
        print(f"❌ Registration error: {e}")
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json() or {}
        if not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Email and password required'}), 400

        email = data['email'].lower().strip()
        session = SessionLocal()
user = session.query(User).filter_by(email=email).first()
session.close()
        ip = get_client_ip()

        if not check_rate_limit(email):
            return jsonify({'error': 'Too many failed attempts'}), 429

        if not user or not user.check_password(data['password']):
            log_login_attempt(email, ip, False)
            session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.commit()
            print(f"❌ Login failed for: {email}")
            return jsonify({'error': 'Invalid email or password'}), 401

        if not user.is_active:
            return jsonify({'error': 'Account disabled'}), 401

        user.last_login = datetime.utcnow()

        # Generate JWT token
        payload = {
            'user_id': user.id,
            'exp': datetime.utcnow() + timedelta(days=7),
            'iat': datetime.utcnow()
        }
        token = jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')

        # Save session
        session = Session(
            user_id=user.id,
            session_token=token,
            ip_address=ip,
            user_agent=request.headers.get('User-Agent', '')[:255],
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.add(session)
        log_login_attempt(email, ip, True)
        session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.commit()

        print(f"✅ Login successful: {email}")

        return jsonify({
            'success': True,
            'message': 'Login successful',
            'token': token,
            'user': user.to_dict()
        }), 200
    except Exception as e:
        session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.rollback()
        print(f"❌ Login error: {e}")
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/auth/logout', methods=['POST'])
@token_required
def logout():
    """Logout user"""
    try:
        if DEV_MODE:
            return jsonify({'message': 'Logged out successfully (dev mode)'}), 200
        
        token = request.headers.get('Authorization').split(" ")[1]
        session = Session.query.filter_by(session_token=token).first()
        if session:
            session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.delete(session)
            session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.commit()
        
        return jsonify({'message': 'Logged out successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/auth/me', methods=['GET'])
@token_required
def get_current_user():
    """Get current user information"""
    try:
        return jsonify({
            'user': g.user.to_dict() if hasattr(g.user, 'to_dict') else {
                'id': g.user.id,
                'email': g.user.email,
                'first_name': g.user.first_name,
                'last_name': g.user.last_name,
                'role': g.user.role
            }
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@auth_bp.route('/auth/users/staff', methods=['GET'])
@admin_required
def get_staff_users():
    """Get all staff users"""
    try:
        staff_roles = ['Sales', 'Production', 'Staff']
        staff_users = User.query.filter(User.role.in_(staff_roles)).order_by(User.first_name).all()
        return jsonify({
            'users': [user.to_dict() for user in staff_users]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/auth/refresh', methods=['POST'])
@token_required
def refresh_token():
    """Refresh JWT token"""
    try:
        if DEV_MODE:
            return jsonify({
                'token': 'mock-jwt-token-123',
                'user': g.user.to_dict() if hasattr(g.user, 'to_dict') else {}
            }), 200
        
        user = g.user
        payload = {
            'user_id': user.id,
            'exp': datetime.utcnow() + timedelta(days=7),
            'iat': datetime.utcnow()
        }
        new_token = jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')
        
        old_token = request.headers.get('Authorization').split(" ")[1]
        session = Session.query.filter_by(session_token=old_token).first()
        if session:
            session.session_token = new_token
            session.expires_at = datetime.utcnow() + timedelta(days=7)
            session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.commit()
        
        return jsonify({
            'token': new_token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.rollback()
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/auth/forgot-password', methods=['POST'])
def forgot_password():
    """Request password reset"""
    try:
        data = request.get_json()
        
        if not data.get('email'):
            return jsonify({'error': 'Email is required'}), 400
        
        email = data['email'].lower().strip()
        session = SessionLocal()
user = session.query(User).filter_by(email=email).first()
session.close()
        
        if user:
            reset_token = user.generate_reset_token()
            session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.commit()
            print(f"Password reset token for {email}: {reset_token}")
        
        return jsonify({
            'message': 'If the email exists, a password reset link has been sent.'
        }), 200
        
    except Exception as e:
        session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.rollback()
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/auth/reset-password', methods=['POST'])
def reset_password():
    """Reset password with token"""
    try:
        data = request.get_json()
        
        required_fields = ['token', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        token = data['token']
        password = data['password']
        
        is_valid, message = validate_password(password)
        if not is_valid:
            return jsonify({'error': message}), 400
        
        user = User.query.filter(
            User.reset_token == token,
            User.reset_token_expires > datetime.utcnow()
        ).first()
        
        if not user:
            return jsonify({'error': 'Invalid or expired reset token'}), 400
        
        user.set_password(password)
        user.reset_token = None
        user.reset_token_expires = None
        
        session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.commit()
        
        return jsonify({'message': 'Password reset successful'}), 200
        
    except Exception as e:
        session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.rollback()
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/auth/change-password', methods=['POST'])
@token_required
def change_password():
    """Change password for authenticated user"""
    try:
        data = request.get_json()
        
        required_fields = ['current_password', 'new_password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        current_password = data['current_password']
        new_password = data['new_password']
        user = g.user
        
        if not user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 400
        
        is_valid, message = validate_password(new_password)
        if not is_valid:
            return jsonify({'error': message}), 400
        
        user.set_password(new_password)
        user.updated_at = datetime.utcnow()
        
        session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.commit()
        
        return jsonify({'message': 'Password changed successfully'}), 200
        
    except Exception as e:
        session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.rollback()
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/auth/users', methods=['GET'])
@admin_required
def get_users():
    """Get all users"""
    try:
        users = User.query.order_by(User.created_at.desc()).all()
        return jsonify({
            'users': [user.to_dict() for user in users]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/auth/users/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    """Toggle user active status"""
    try:
        user = User.query.get_or_404(user_id)
        user.is_active = not user.is_active
        user.updated_at = datetime.utcnow()
        session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.commit()
        
        return jsonify({
            'message': f'User {"activated" if user.is_active else "deactivated"} successfully',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        session = SessionLocal()
# ...do stuff...
session.add(...)
session.commit()
session.close()
.rollback()
        return jsonify({'error': str(e)}), 500