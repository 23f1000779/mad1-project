from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, current_app
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from .models import db, User, DoctorProfile, PatientProfile, Department, Appointment, Treatment
from .utils import validate_csrf
from datetime import datetime,timedelta, date
from sqlalchemy.exc import IntegrityError

views = Blueprint('views', __name__)

@views.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('main.admin_dashboard'))
        if current_user.role == 'doctor':
            return redirect(url_for('main.doctor_dashboard'))
        if current_user.role == 'patient':
            return redirect(url_for('main.patient_dashboard'))
    return render_template('index.html')


# ----------------------
# Token helpers
# ----------------------
def get_serializer(secret_key=None):
    key = secret_key or current_app.config.get('SECRET_KEY')
    return URLSafeTimedSerializer(key)


def generate_password_reset_token(user_email):
    s = get_serializer()
    return s.dumps(user_email, salt='password-reset-salt')


def verify_password_reset_token(token, max_age=3600):
    s = get_serializer()
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=max_age)
        return email
    except SignatureExpired:
        return None
    except BadSignature:
        return None


# ---------- AUTH ----------
@views.route('/login', methods=['GET', 'POST'])
def login():

    # if already logged in, redirect to dashboard or next
    if current_user.is_authenticated:
        next_url = request.args.get('next') or url_for('views.index')
        return redirect(next_url)

    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        remember = bool(request.form.get('remember'))

        if not email or not password:
            flash('Please enter both email and password.', 'warning')
            return render_template('login.html', csrf_token=getattr(request, 'csrf_token', None))

        user = User.query.filter_by(email=email).first()
        if not user:
            flash('Invalid email or password.', 'danger')
            return render_template('login.html', csrf_token=getattr(request, 'csrf_token', None))

        # Use either provided check_password method or werkzeug check
        try:
            password_ok = False
            if hasattr(user, 'check_password'):
                password_ok = user.check_password(password)
            elif hasattr(user, 'password_hash'):
                password_ok = check_password_hash(user.password_hash, password)
            else:
                password_ok = False
        except Exception:
            current_app.logger.exception("Error checking password")
            password_ok = False

        if not password_ok:
            flash('Invalid email or password.', 'danger')
            return render_template('login.html', csrf_token=getattr(request, 'csrf_token', None))

        # Optional: check is_active
        if hasattr(user, 'is_active') and not getattr(user, 'is_active'):
            flash('Account is inactive. Contact admin.', 'danger')
            return render_template('login.html', csrf_token=getattr(request, 'csrf_token', None))

        # Log in
        login_user(user, remember=remember, duration=timedelta(days=30))
        flash('Logged in successfully.', 'success')

        # Safely handle next
        next_url = request.args.get('next') or request.form.get('next') or url_for('views.index')
        return redirect(next_url)

    # GET
    return render_template('login.html', csrf_token=getattr(request, 'csrf_token', None))



@views.route('/register/patient', methods=['GET', 'POST'])
def register_patient():
    if request.method == 'POST':
        payload=request.form
        name = (payload.get('name') or '').strip()
        email = (payload.get('email') or '').strip().lower()
        password = payload.get('password') or ''
        contact = (payload.get('contact') or '').strip()
        dob_raw = payload.get('dob') or None

        if not name or not email or not password:
            flash('Name, email and password are required', 'danger')
            return render_template('register_patient.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters', 'danger')
            return render_template('register_patient.html')

        dob = None
        if dob_raw:
            try:
                dob = datetime.strptime(dob_raw, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date of birth format', 'danger')
                return render_template('register_patient.html')

        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return render_template('register_patient.html')

        user = User(email=email, name=name, role='patient')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        patient = PatientProfile(user_id=user.id, contact=contact, dob=dob)
        db.session.add(patient)
        db.session.commit()

        flash('Registration successful. Please login.', 'success')
        return redirect(url_for('views.login'))

    return render_template('register_patient.html')

@views.route('/register/doctor', methods=['GET', 'POST'])
def register_doctor():
    if request.method == 'POST':
        payload=request.form
        name = (payload.get('name') or '').strip()
        email = (payload.get('email') or '').strip().lower()
        password = payload.get('password') or ''
        specialization = (payload.get('specialization') or '').strip()

        if not name or not email or not password:
            flash('Name, email and password are required', 'danger')
            return render_template('register_doctor.html')

        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return render_template('register_doctor.html')

        user = User(email=email, name=name, role='doctor')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        doctor = DoctorProfile(user_id=user.id, specialization=specialization)
        db.session.add(doctor)
        db.session.commit()

        flash('Doctor registration successful. Please login.', 'success')
        return redirect(url_for('views.login'))

    return render_template('register_doctor.html')

@views.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('views.login'))

@views.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        if not email:
            flash('Please enter your email address.', 'warning')
            return render_template('forgot_password.html', csrf_token=getattr(request, 'csrf_token', None))

        user = User.query.filter_by(email=email).first()
        if not user:
            # Do not reveal whether email exists — respond generically
            flash('If the email exists in our system, you will receive password reset instructions shortly.', 'info')
            return render_template('forgot_password.html', csrf_token=getattr(request, 'csrf_token', None))

        try:
            token = generate_password_reset_token(user.email)
            reset_url = url_for('views.reset_password', token=token, _external=True)
            body = f"Hello,\n\nTo reset your password click the link below (valid for 1 hour):\n\n{reset_url}\n\nIf you did not request this, ignore.\n"
            send_email(user.email, "Password reset", body)
            flash('If the email exists in our system, you will receive password reset instructions shortly.', 'info')
            return render_template('forgot_password.html', csrf_token=getattr(request, 'csrf_token', None))
        except Exception:
            current_app.logger.exception("Failed to initiate password reset")
            flash('Could not send reset email. Try again later.', 'danger')
            return render_template('forgot_password.html', csrf_token=getattr(request, 'csrf_token', None))

    return render_template('forgot_password.html', csrf_token=getattr(request, 'csrf_token', None))

@views.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # Verify token (1 hour)
    email = verify_password_reset_token(token, max_age=current_app.config.get('PASSWORD_RESET_TIMEOUT', 3600))
    if not email:
        flash('Reset link is invalid or expired.', 'danger')
        return redirect(url_for('views.forgot_password'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Invalid reset link (user not found).', 'danger')
        return redirect(url_for('views.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm') or ''
        if not password:
            flash('Please provide a new password.', 'warning')
            return render_template('reset_password.html', token=token, csrf_token=getattr(request, 'csrf_token', None))
        if password != confirm:
            flash('Passwords do not match.', 'warning')
            return render_template('reset_password.html', token=token, csrf_token=getattr(request, 'csrf_token', None))

        try:
            if hasattr(user, 'set_password'):
                user.set_password(password)
            else:
                user.password_hash = generate_password_hash(password)
            db.session.add(user)
            db.session.commit()
            flash('Password updated. You may now log in.', 'success')
            return redirect(url_for('views.login'))
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to reset password")
            flash('Failed to reset password. Try again later.', 'danger')
            return render_template('reset_password.html', token=token, csrf_token=getattr(request, 'csrf_token', None))

    # GET -> render reset form
    return render_template('reset_password.html', token=token, csrf_token=getattr(request, 'csrf_token', None))
