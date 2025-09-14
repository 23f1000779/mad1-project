from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from .models import db, User, DoctorProfile, PatientProfile, Department, Appointment, Treatment
from .repositories import userRepository, departmentRepository, doctorProfileRepository
from .utils import validate_csrf
from datetime import datetime, date
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

# ---------- AUTH ----------
@views.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        payload=request.form 
        email = (payload.get('email') or '').strip().lower()
        password = payload.get('password') or ''
        if not email or not password:
            flash('Email and password are required', 'danger')
            return render_template('login.html')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.active:
            login_user(user)
            flash('Logged in successfully', 'success')
            return redirect(url_for('views.index'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@views.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        payload=request.form
        name = (payload.get('name') or '').strip()
        email = (payload.get('email') or '').strip().lower()
        password = payload.get('password') or ''
        contact = (payload.get('contact') or '').strip()
        dob_raw = payload.get('dob') or None

        if not name or not email or not password:
            flash('Name, email and password are required', 'danger')
            return render_template('register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters', 'danger')
            return render_template('register.html')

        dob = None
        if dob_raw:
            try:
                dob = datetime.strptime(dob_raw, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date of birth format', 'danger')
                return render_template('register.html')

        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return render_template('register.html')

        user = User(email=email, name=name, role='patient')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        patient = PatientProfile(user_id=user.id, contact=contact, dob=dob)
        db.session.add(patient)
        db.session.commit()

        flash('Registration successful. Please login.', 'success')
        return redirect(url_for('views.login'))

    return render_template('register.html')

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
