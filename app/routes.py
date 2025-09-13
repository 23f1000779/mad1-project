from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from .models import db, User, DoctorProfile, PatientProfile, Department, Appointment, Treatment
from .utils import validate_csrf
from datetime import datetime, date
from sqlalchemy.exc import IntegrityError

main = Blueprint('main', __name__)

def role_required(role):
    from functools import wraps
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != role:
                flash('Access denied', 'danger')
                return redirect(url_for('main.login'))
            return fn(*args, **kwargs)
        return wrapper
    return decorator

@main.route('/')
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
@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        if not email or not password:
            flash('Email and password are required', 'danger')
            return render_template('login.html')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.active:
            login_user(user)
            flash('Logged in successfully', 'success')
            return redirect(url_for('main.index'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out', 'info')
    return redirect(url_for('main.login'))

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        contact = (request.form.get('contact') or '').strip()
        dob_raw = request.form.get('dob') or None

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
        return redirect(url_for('main.login'))

    return render_template('register.html')

# ---------- ADMIN ----------
@main.route('/admin')
@login_required
@role_required('admin')
def admin_dashboard():
    total_doctors = DoctorProfile.query.count()
    total_patients = PatientProfile.query.count()
    total_appointments = Appointment.query.count()
    return render_template('admin_dashboard.html',
                           doctors=total_doctors,
                           patients=total_patients,
                           appointments=total_appointments)

@main.route('/admin/doctors/add', methods=['GET', 'POST'])
@login_required
@role_required('admin')
@validate_csrf
def add_doctor():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        specialization = (request.form.get('specialization') or '').strip()
        bio = (request.form.get('bio') or '').strip()

        if not name or not email:
            flash('Name and email required', 'danger')
            return render_template('doctor_profile.html')

        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return render_template('doctor_profile.html')

        user = User(email=email, name=name, role='doctor')
        user.set_password('Doctor@123')
        db.session.add(user)
        db.session.commit()

        doc = DoctorProfile(user_id=user.id, specialization=specialization, bio=bio)
        db.session.add(doc)
        db.session.commit()

        flash('Doctor added successfully. Default password: Doctor@123', 'success')
        return redirect(url_for('main.admin_dashboard'))

    return render_template('doctor_profile.html')

@main.route('/admin/doctors/<int:doctor_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
@validate_csrf
def edit_doctor(doctor_id):
    doc = DoctorProfile.query.get_or_404(doctor_id)
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        specialization = (request.form.get('specialization') or '').strip()
        bio = (request.form.get('bio') or '').strip()

        if not name:
            flash('Name is required', 'danger')
            return render_template('doctor_profile.html', doctor=doc)

        doc.user.name = name
        doc.specialization = specialization
        doc.bio = bio
        db.session.commit()

        flash('Doctor updated', 'success')
        return redirect(url_for('main.admin_dashboard'))

    return render_template('doctor_profile.html', doctor=doc)

@main.route('/admin/doctors/<int:doctor_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
@validate_csrf
def delete_doctor(doctor_id):
    doc = DoctorProfile.query.get_or_404(doctor_id)
    doc.user.active = False
    db.session.commit()
    flash('Doctor deactivated', 'info')
    return redirect(url_for('main.admin_dashboard'))

@main.route('/admin/patients/add', methods=['GET', 'POST'])
@login_required
@role_required('admin')
@validate_csrf
def add_patient():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        contact = (request.form.get('contact') or '').strip()

        if not name or not email:
            flash('Name and email required', 'danger')
            return render_template('patient_profile.html')

        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return render_template('patient_profile.html')

        user = User(email=email, name=name, role='patient')
        user.set_password('Patient@123')
        db.session.add(user)
        db.session.commit()

        pat = PatientProfile(user_id=user.id, contact=contact)
        db.session.add(pat)
        db.session.commit()

        flash('Patient added with default password: Patient@123', 'success')
        return redirect(url_for('main.admin_dashboard'))

    return render_template('patient_profile.html')

@main.route('/admin/patients/<int:patient_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
@validate_csrf
def edit_patient(patient_id):
    pat = PatientProfile.query.get_or_404(patient_id)
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        contact = (request.form.get('contact') or '').strip()

        if not name:
            flash('Name required', 'danger')
            return render_template('patient_profile.html', patient=pat)

        pat.user.name = name
        pat.contact = contact
        db.session.commit()

        flash('Patient updated', 'success')
        return redirect(url_for('main.admin_dashboard'))

    return render_template('patient_profile.html', patient=pat)

@main.route('/admin/patients/<int:patient_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
@validate_csrf
def delete_patient(patient_id):
    pat = PatientProfile.query.get_or_404(patient_id)
    pat.user.active = False
    db.session.commit()
    flash('Patient deactivated', 'info')
    return redirect(url_for('main.admin_dashboard'))

@main.route('/admin/appointments')
@login_required
@role_required('admin')
def admin_appointments():
    appts = Appointment.query.order_by(Appointment.date.desc(), Appointment.time.desc()).all()
    return render_template('appointment_list.html', appointments=appts)

# ---------- DOCTOR ----------
@main.route('/doctor')
@login_required
@role_required('doctor')
def doctor_dashboard():
    doc = current_user.doctor
    if not doc:
        flash('Doctor profile missing', 'danger')
        return redirect(url_for('main.logout'))
    appts = Appointment.query.filter_by(doctor_id=doc.id).order_by(Appointment.date, Appointment.time).all()
    patients = {a.patient for a in appts}
    return render_template('doctor_dashboard.html', appointments=appts, doctor=doc, patients=patients)

@main.route('/doctor/appointment/<int:appt_id>/complete', methods=['GET', 'POST'])
@login_required
@role_required('doctor')
@validate_csrf
def complete_appointment(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    doc_profile = current_user.doctor
    if appt.doctor_id != doc_profile.id:
        flash('Access denied', 'danger')
        return redirect(url_for('main.doctor_dashboard'))

    if request.method == 'POST':
        diagnosis = (request.form.get('diagnosis') or '').strip()
        prescription = (request.form.get('prescription') or '').strip()
        notes = (request.form.get('notes') or '').strip()

        if not diagnosis:
            flash('Diagnosis is required', 'danger')
            return render_template('treatment_form.html', appointment=appt)

        if appt.treatment:
            appt.treatment.diagnosis = diagnosis
            appt.treatment.prescription = prescription
            appt.treatment.notes = notes
        else:
            tr = Treatment(appointment_id=appt.id, diagnosis=diagnosis, prescription=prescription, notes=notes)
            db.session.add(tr)

        appt.status = 'Completed'
        db.session.commit()
        flash('Treatment saved and appointment marked completed', 'success')
        return redirect(url_for('main.doctor_dashboard'))

    return render_template('treatment_form.html', appointment=appt)

@main.route('/doctor/appointment/<int:appt_id>/cancel', methods=['POST'])
@login_required
@role_required('doctor')
@validate_csrf
def doctor_cancel_appointment(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    if appt.doctor.user_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('main.doctor_dashboard'))
    appt.status = 'Cancelled'
    db.session.commit()
    flash('Appointment cancelled', 'info')
    return redirect(url_for('main.doctor_dashboard'))

# ---------- PATIENT ----------
@main.route('/patient')
@login_required
@role_required('patient')
def patient_dashboard():
    pat = current_user.patient
    departments = Department.query.all()
    upcoming = Appointment.query.filter_by(patient_id=pat.id).filter(Appointment.status != 'Cancelled').order_by(Appointment.date, Appointment.time).all()
    past = Appointment.query.filter_by(patient_id=pat.id).filter(Appointment.status == 'Completed').order_by(Appointment.date.desc(), Appointment.time.desc()).all()
    return render_template('patient_dashboard.html', patient=pat, departments=departments, upcoming=upcoming, past=past)

@main.route('/patient/book', methods=['GET', 'POST'])
@login_required
@role_required('patient')
@validate_csrf
def book_appointment():
    if request.method == 'POST':
        try:
            doctor_id = int(request.form.get('doctor_id'))
            date_str = request.form.get('date')
            time_str = request.form.get('time')
            if not date_str or not time_str:
                flash('Date and time required', 'danger')
                return redirect(url_for('main.book_appointment'))
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            time_obj = datetime.strptime(time_str, '%H:%M').time()
        except (ValueError, TypeError):
            flash('Invalid input', 'danger')
            return redirect(url_for('main.book_appointment'))

        dt = datetime.combine(date_obj, time_obj)
        if dt < datetime.now():
            flash('Cannot book an appointment in the past', 'danger')
            return redirect(url_for('main.book_appointment'))

        conflict = Appointment.query.filter_by(doctor_id=doctor_id, date=date_obj, time=time_obj).first()
        if conflict:
            flash('Selected slot already booked', 'danger')
            return redirect(url_for('main.book_appointment'))

        appt = Appointment(patient_id=current_user.patient.id, doctor_id=doctor_id, date=date_obj, time=time_obj, status='Booked')
        db.session.add(appt)
        try:
            db.session.commit()
            flash('Appointment booked', 'success')
            return redirect(url_for('main.patient_dashboard'))
        except IntegrityError:
            db.session.rollback()
            flash('Failed to book. Possible conflict', 'danger')
            return redirect(url_for('main.book_appointment'))

    doctors = DoctorProfile.query.all()
    return render_template('appointment_form.html', doctors=doctors)

@main.route('/patient/appointment/<int:appt_id>/reschedule', methods=['POST'])
@login_required
@role_required('patient')
@validate_csrf
def reschedule_appointment(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    if appt.patient.user_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('main.patient_dashboard'))

    try:
        date_str = request.form.get('date')
        time_str = request.form.get('time')
        doctor_id = int(request.form.get('doctor_id') or appt.doctor_id)
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        time_obj = datetime.strptime(time_str, '%H:%M').time()
    except (ValueError, TypeError):
        flash('Invalid input for reschedule', 'danger')
        return redirect(url_for('main.patient_dashboard'))

    conflict = Appointment.query.filter_by(doctor_id=doctor_id, date=date_obj, time=time_obj).first()
    if conflict and conflict.id != appt.id:
        flash('Selected slot already booked', 'danger')
        return redirect(url_for('main.patient_dashboard'))

    appt.date = date_obj
    appt.time = time_obj
    appt.doctor_id = doctor_id
    appt.status = 'Booked'
    try:
        db.session.commit()
        flash('Appointment rescheduled', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Failed to reschedule due to conflict', 'danger')

    return redirect(url_for('main.patient_dashboard'))

@main.route('/patient/appointment/<int:appt_id>/cancel', methods=['POST'])
@login_required
@role_required('patient')
@validate_csrf
def cancel_appointment(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    if appt.patient.user_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('main.patient_dashboard'))
    appt.status = 'Cancelled'
    db.session.commit()
    flash('Appointment cancelled', 'info')
    return redirect(url_for('main.patient_dashboard'))

# ---------- SEARCH & VIEWS ----------
@main.route('/search')
@login_required
def search():
    q = (request.args.get('q') or '').strip()
    by = request.args.get('by') or 'doctor'
    if not q:
        flash('Enter search text', 'warning')
        return redirect(url_for('main.index'))

    if by == 'doctor':
        docs = DoctorProfile.query.join(User).filter(
            (User.name.ilike(f'%{q}%')) | (DoctorProfile.specialization.ilike(f'%{q}%'))
        ).all()
        return render_template('list_doctors.html', doctors=docs, q=q)
    else:
        pats = PatientProfile.query.join(User).filter(
            (User.name.ilike(f'%{q}%')) | (PatientProfile.contact.ilike(f'%{q}%'))
        ).all()
        return render_template('list_patients.html', patients=pats, q=q)

@main.route('/doctors')
@login_required
def list_all_doctors():
    docs = DoctorProfile.query.all()
    return render_template('list_doctors.html', doctors=docs)

@main.route('/doctors/<int:doctor_id>')
@login_required
def view_doctor(doctor_id):
    doc = DoctorProfile.query.get_or_404(doctor_id)
    return render_template('doctor_profile_view.html', doctor=doc)

@main.route('/patients/<int:patient_id>')
@login_required
def view_patient(patient_id):
    pat = PatientProfile.query.get_or_404(patient_id)
    if current_user.role == 'admin' or (current_user.role == 'patient' and current_user.patient.id == pat.id):
        return render_template('patient_profile_view.html', patient=pat)
    if current_user.role == 'doctor':
        from sqlalchemy import exists
        has = db.session.query(exists().where(Appointment.doctor_id == current_user.doctor.id).where(Appointment.patient_id == pat.id)).scalar()
        if has:
            return render_template('patient_profile_view.html', patient=pat)
    flash('Access denied to view patient', 'danger')
    return redirect(url_for('main.index'))

# ---------- SMALL JSON API (session-protected example) ----------
@main.route('/api/doctor/<int:doc_id>/appointments')
@login_required
def api_doctor_appointments(doc_id):
    appts = Appointment.query.filter_by(doctor_id=doc_id).all()
    out = []
    for a in appts:
        out.append({
            'id': a.id,
            'date': a.date.isoformat(),
            'time': a.time.strftime('%H:%M'),
            'status': a.status,
            'patient_name': a.patient.user.name
        })
    return jsonify(out)
