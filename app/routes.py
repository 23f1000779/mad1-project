from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app, g
from flask_login import login_user, logout_user, login_required, current_user
from math import ceil
from datetime import time, datetime, date, timedelta
import json, re

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import joinedload

from .models import db, User, DoctorProfile, PatientProfile, Department, Appointment, Treatment, DoctorAvailability

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
                return redirect(url_for('views.login'))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out', 'info')
    return redirect(url_for('views.login'))


ITEMS_PER_PAGE = 8  # tune as needed

def paginate_query(query, page, per_page=ITEMS_PER_PAGE):
    """Return (items, pagination dict) for a SQLAlchemy query."""
    page = max(1, int(page or 1))
    per_page = int(per_page)
    total = query.order_by(None).count()  
    total_pages = max(1, ceil(total / per_page))
    if page > total_pages:
        page = total_pages
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_page': page - 1 if page > 1 else None,
        'next_page': page + 1 if page < total_pages else None
    }
    return items, pagination



# ---------- ADMIN ----------
@main.route('/admin')
@login_required
@role_required('admin')
def admin_dashboard():
    total_doctors = DoctorProfile.query.count()
    total_patients = PatientProfile.query.count()
    total_appointments = Appointment.query.count()
    total_departments = Department.query.count()

    
    # provide lists for quick admin actions (limit to last 50 to avoid huge pages)
    doctors_list = DoctorProfile.query.order_by(DoctorProfile.id.desc()).limit(50).all()
    patients_list = PatientProfile.query.order_by(PatientProfile.id.desc()).limit(50).all()

    return render_template('admin_dashboard.html',
                           doctors=total_doctors,
                           patients=total_patients,
                           appointments=total_appointments,
                           departments=total_departments,
                           doctors_list=doctors_list,
                           patients_list=patients_list)

@main.route('/admin/departments')
@login_required
@role_required('admin')
def list_departments():
    depts = Department.query.order_by(Department.name).all()
    return render_template('department_list.html', departments=depts)

@main.route('/admin/departments/add', methods=['GET', 'POST'])
@login_required
@role_required('admin')
@validate_csrf
def add_department():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        description = (request.form.get('description') or '').strip()
        if not name:
            flash('Department name is required', 'danger')
            return render_template('department_form.html')
        if Department.query.filter_by(name=name).first():
            flash('Department with this name already exists', 'danger')
            return render_template('department_form.html')
        dept = Department(name=name, description=description)
        db.session.add(dept)
        db.session.commit()
        flash('Department added', 'success')
        return redirect(url_for('main.list_departments'))
    return render_template('department_form.html')

@main.route('/admin/departments/<int:dept_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
@validate_csrf
def edit_department(dept_id):
    dept = Department.query.get_or_404(dept_id)
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        description = (request.form.get('description') or '').strip()
        if not name:
            flash('Name required', 'danger')
            return render_template('department_form.html', department=dept)
        # check uniqueness
        other = Department.query.filter(Department.name==name, Department.id!=dept.id).first()
        if other:
            flash('Another department with this name exists', 'danger')
            return render_template('department_form.html', department=dept)
        dept.name = name
        dept.description = description
        db.session.commit()
        flash('Department updated', 'success')
        return redirect(url_for('main.list_departments'))
    return render_template('department_form.html', department=dept)

@main.route('/admin/departments/<int:dept_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
@validate_csrf
def delete_department(dept_id):
    dept = Department.query.get_or_404(dept_id)
    # optional: prevent delete if doctors exist
    if dept.doctors.count() > 0:
        flash('Cannot delete department with registered doctors. Reassign or remove doctors first.', 'danger')
        return redirect(url_for('main.list_departments'))
    db.session.delete(dept)
    db.session.commit()
    flash('Department deleted', 'info')
    return redirect(url_for('main.list_departments'))

@main.route('/admin/doctors')
@login_required
@role_required('admin')
def list_doctors():
    doctors= DoctorProfile.query.order_by(DoctorProfile.id.desc()).all()
    return render_template('doctors_list.html', doctors=doctors)


@main.route('/admin/doctors/add', methods=['GET', 'POST'])
@login_required
@role_required('admin')
@validate_csrf
def add_doctor():
    depts = Department.query.order_by(Department.name).all()
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        specialization = (request.form.get('specialization') or '').strip()
        qualification = (request.form.get('qualification') or '').strip()
        experience = (request.form.get('experience') or '').strip()
        bio = (request.form.get('bio') or '').strip()
        dept_id = request.form.get('department_id') or None

        if not name or not email:
            flash('Name and email required', 'danger')
            return render_template('doctor_profile.html', departments=depts)

        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return render_template('doctor_profile.html', departments=depts)

        user = User(email=email, name=name, role='doctor')
        user.set_password('Doctor@123')
        db.session.add(user)
        db.session.commit()

        doc = DoctorProfile(user_id=user.id, specialization=specialization,qualification=qualification, experience=experience, bio=bio)
        if dept_id:
            try:
                doc.department_id = int(dept_id)
            except ValueError:
                doc.department_id = None
        db.session.add(doc)
        db.session.commit()
        flash('Doctor added successfully. Default password: Doctor@123', 'success')
        return redirect(url_for('main.admin_dashboard'))

    return render_template('doctor_profile.html', departments=depts)
@main.route('/admin/doctors/<int:doctor_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
@validate_csrf
def edit_doctor(doctor_id):
    doc = DoctorProfile.query.get_or_404(doctor_id)
    depts = Department.query.order_by(Department.name).all()
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        specialization = (request.form.get('specialization') or '').strip()
        qualification = (request.form.get('qualification') or '').strip()
        experience = (request.form.get('experience') or '').strip()
        bio = (request.form.get('bio') or '').strip()
        dept_id = request.form.get('department_id') or None

        if not name:
            flash('Name is required', 'danger')
            return render_template('doctor_profile.html', doctor=doc, departments=depts)

        doc.user.name = name
        doc.specialization = specialization
        doc.qualification = qualification
        doc.experience = experience
        doc.bio = bio
        if dept_id:
            try:
                doc.department_id = int(dept_id)
            except ValueError:
                doc.department_id = None
        else:
            doc.department_id = None

        db.session.commit()
        flash('Doctor updated', 'success')
        return redirect(url_for('main.admin_dashboard'))
    return render_template('doctor_profile.html', doctor=doc, departments=depts)

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

@main.route('/admin/patients')
@login_required
@role_required('admin')
def list_patients():
    pats = PatientProfile.query.order_by(PatientProfile.id.desc()).all()
    return render_template('patients_list.html', patients=pats)

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


@main.route('/admin/doctor/<int:doctor_id>/view')
@login_required
@role_required('admin')
@validate_csrf
def admin_view_doctor(doctor_id):
    return_url = request.args.get('next') or request.referrer

    # Determine page from querystring
    page = request.args.get('page', 1, type=int)

    # # Load doctor basic info
    # from .models import DoctorProfile, Appointment  # import inline to avoid circulars
    try:
        doctor = (
            DoctorProfile.query.get_or_404(doctor_id)
        )
    except Exception:
        current_app.logger.exception("Failed doctor eager-load; falling back.")
        doctor = DoctorProfile.query.get_or_404(doctor_id)

    # Build appointment query for this doctor (upcoming and past both)
    appt_q = (Appointment.query
              .filter_by(doctor_id=doctor.id)
              .order_by(Appointment.date.desc(), Appointment.time.desc()))  # show recent first

    appointments, pagination = paginate_query(appt_q, page)

    return render_template(
        'doctor_profile_view.html',
        doctor=doctor,
        appointments=appointments,
        pagination=pagination,
        next=return_url
    )


@main.route('/admin/doctor/<int:doctor_id>/blacklist', methods=['POST'])
@login_required
@role_required('admin')
@validate_csrf
def admin_blacklist_doctor(doctor_id):
    """
    Blacklist a doctor. Requires a non-empty 'reason' in POST data.
    Sets: is_blacklisted=True, blacklist_reason, blacklisted_at, blacklisted_by
    """
    doctor = DoctorProfile.query.get_or_404(doctor_id)
    reason = (request.form.get('reason') or '').strip()

    if not reason or len(reason) < 3:
        flash('Please provide a valid reason for blacklisting (at least 3 characters).', 'warning')
        # return back to doctor view page
        return redirect(request.referrer or url_for('main.admin_view_doctor', doctor_id=doctor.id))

    try:
        # defensive attribute setting in case columns don't exist exactly
        setattr(doctor, 'is_blacklisted', True)
        setattr(doctor, 'blacklist_reason', reason)
        setattr(doctor, 'blacklisted_at', datetime.utcnow())
        setattr(doctor, 'blacklisted_by', getattr(current_user, 'id', None))

        db.session.add(doctor)
        db.session.commit()

        flash(f"Doctor {getattr(doctor, 'user').name if getattr(doctor, 'user', None) else doctor.id} has been blacklisted.", 'danger')
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to blacklist doctor")
        flash('Failed to blacklist doctor. Please try again.', 'danger')

    return redirect(request.referrer or url_for('main.admin_view_doctor', doctor_id=doctor.id))


@main.route('/admin/doctor/<int:doctor_id>/whitelist', methods=['POST'])
@login_required
@role_required('admin')
@validate_csrf
def admin_whitelist_doctor(doctor_id):
    """
    Remove doctor from blacklist.
    Clears: is_blacklisted, blacklist_reason, blacklisted_at, blacklisted_by
    """
    doctor = DoctorProfile.query.get_or_404(doctor_id)

    try:
        setattr(doctor, 'is_blacklisted', False)
        setattr(doctor, 'blacklist_reason', None)
        setattr(doctor, 'blacklisted_at', None)
        setattr(doctor, 'blacklisted_by', None)

        db.session.add(doctor)
        db.session.commit()

        flash(f"Doctor {getattr(doctor, 'user').name if getattr(doctor, 'user', None) else doctor.id} has been whitelisted.", 'success')
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to whitelist doctor")
        flash('Failed to whitelist doctor. Please try again.', 'danger')

    return redirect(request.referrer or url_for('main.admin_view_doctor', doctor_id=doctor.id))


@main.route('/admin/patient/<int:patient_id>/blacklist', methods=['POST'])
@login_required
@role_required('admin')
@validate_csrf
def admin_blacklist_patient(patient_id):
    patient = PatientProfile.query.get_or_404(patient_id)
    reason = (request.form.get('reason') or '').strip()

    if not reason or len(reason) < 3:
        flash('Please provide a valid reason for blacklisting (at least 3 characters).', 'warning')
        # return back to doctor view page
        return redirect(request.referrer or url_for('main.admin_view_patient', patient_id=patient.id))

    try:
        # defensive attribute setting in case columns don't exist exactly
        setattr(patient, 'is_blacklisted', True)
        setattr(patient, 'blacklist_reason', reason)
        setattr(patient, 'blacklisted_at', datetime.utcnow())
        setattr(patient, 'blacklisted_by', getattr(current_user, 'id', None))

        db.session.add(patient)
        db.session.commit()

        flash(f"Patient {getattr(patient, 'user').name if getattr(patient, 'user', None) else patient.id} has been blacklisted.", 'danger')
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to blacklist patient")
        flash('Failed to blacklist patient. Please try again.', 'danger')

    return redirect(request.referrer or url_for('main.admin_view_patient', patient_id=patient.id))


@main.route('/admin/patient/<int:patient_id>/whitelist', methods=['POST'])
@login_required
@role_required('admin')
@validate_csrf
def admin_whitelist_patient(patient_id):
    patient = PatientProfile.query.get_or_404(patient_id)
    reason = (request.form.get('reason') or '').strip()

    if not reason or len(reason) < 3:
        flash('Please provide a valid reason for blacklisting (at least 3 characters).', 'warning')
        # return back to doctor view page
        return redirect(request.referrer or url_for('main.admin_view_patient', patient_id=patient.id))

    try:
        # defensive attribute setting in case columns don't exist exactly
        setattr(patient, 'is_blacklisted', False)
        setattr(patient, 'blacklist_reason', None)
        setattr(patient, 'blacklisted_at', None)
        setattr(patient, 'blacklisted_by', None)

        db.session.add(patient)
        db.session.commit()

        flash(f"Patient {getattr(patient, 'user').name if getattr(patient, 'user', None) else patient.id} has been whitelisted.", 'success')
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to whitelist patient")
        flash('Failed to whitelist patient. Please try again.', 'danger')

    return redirect(request.referrer or url_for('main.admin_view_patient', patient_id=patient.id))


@main.route('/admin/patient/<int:patient_id>/view')
@login_required
@role_required('admin')
@validate_csrf
def admin_view_patient(patient_id):
    return_url = request.args.get('next') or request.referrer
    page = request.args.get('page', 1, type=int)

    from .models import PatientProfile, Appointment
    try:
        patient = (
            PatientProfile.query.get_or_404(patient_id)
        )
    except Exception:
        current_app.logger.exception("Failed patient eager-load; falling back.")
        patient = PatientProfile.query.get_or_404(patient_id)

    appt_q = (Appointment.query
              .filter_by(patient_id=patient.id)
              .order_by(Appointment.date.desc(), Appointment.time.desc()))

    appointments, pagination = paginate_query(appt_q, page)

    return render_template(
        'patient_profile_view.html',
        patient=patient,
        appointments=appointments,
        pagination=pagination,
        next=return_url,
        csrf_token=getattr(g, 'csrf_token', None)
    )

@main.route('/admin/appointments')
@login_required
@role_required('admin')
@validate_csrf
def admin_appointments():
    q = Appointment.query
    # filters
    qstr = request.args.get('q')
    status = request.args.get('status')
    date_f = request.args.get('date')
    if qstr:
        q = q.join(PatientProfile).join(User).filter((User.name.ilike(f'%{qstr}%')) | (Appointment.id==qstr))
    if status:
        q = q.filter(Appointment.status==status)
    if date_f:
        try:
            d = datetime.strptime(date_f, '%Y-%m-%d').date()
            q = q.filter(Appointment.date==d)
        except:
            pass
    appointments = q.order_by(Appointment.date.desc(), Appointment.time.desc()).all()
    return render_template('appointment_list.html', appointments=appointments)

# Helper to safely retrieve appointment and check permissions (optional)
def get_appt_or_404(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    return appt

@main.route('/admin/appointment/<int:appt_id>/view')
@login_required
@validate_csrf
def admin_appointment_view(appt_id):

    # Load appointment or return 404
    appointment = Appointment.query.get_or_404(appt_id)

    # Optional "return to previous page" logic
    return_url = request.args.get("next") or request.referrer

    return render_template(
        "admin_appointment_view.html",
        appointment=appointment,
        next=return_url
    )


@main.route('/admin/appointment/create', methods=['GET', 'POST'])
@login_required
@role_required('admin')
@validate_csrf
def admin_create_appointment():
  
    return_url = request.args.get('next')
    # populate selects for GET and for re-render after validation errors

    try:
        patients = (
            PatientProfile.query
            .join(User, PatientProfile.user)        # Patient.user relationship -> User
            .order_by(User.name)
            .all()
        )
    except Exception:
        # Fallback: if relationship naming differs, just fetch unsorted list
        # current_app.logger.exception("Failed to query patients with join(User). Falling back to unsorted query.")
        patients = PatientProfile.query.all()

    try:
        doctors = (
            DoctorProfile.query
            .join(User, DoctorProfile.user)        # Doctor.user relationship -> User
            .order_by(User.name)
            .all()
        )
    except Exception:
        # current_app.logger.exception("Failed to query doctors with join(User). Falling back to unsorted query.")
        doctors = DoctorProfile.query.all()

    if request.method == 'POST':
        # Basic server-side validation + parsing
        patient_id = request.form.get('patient_id')
        doctor_id = request.form.get('doctor_id')
        date_str = request.form.get('date')
        time_str = request.form.get('time')

        # Validate presence
        if not patient_id or not doctor_id or not date_str or not time_str:
            flash('Please fill all required fields.', 'warning')
            return render_template('admin_appointment_form.html',patients=patients, doctors=doctors,next=return_url)

        # Ensure IDs are ints
        try:
            patient_id = int(patient_id)
            doctor_id = int(doctor_id)
        except ValueError:
            flash('Invalid patient or doctor selected.', 'danger')
            return render_template('admin_appointment_form.html',patients=patients, doctors=doctors,next=return_url)

        try:
            appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            appt_time = datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            flash('Invalid date or time format.', 'danger')
            return render_template('admin_appointment_form.html',patients=patients, doctors=doctors,next=return_url)
        # Prevent booking in the past (server-side)
        now_dt = datetime.utcnow()
        chosen_dt = datetime.combine(appt_date, appt_time)
        # If your app uses local timezone, convert appropriately instead of using UTC directly.
        if chosen_dt < now_dt:
            flash('Selected date/time is in the past. Please choose a future time.', 'danger')
            return render_template('admin_appointment_form.html',patients=patients, doctors=doctors,next=return_url)
        
        # Ensure patient and doctor exist
        patient = PatientProfile.query.get(patient_id)
        doctor = DoctorProfile.query.get(doctor_id)
        if not patient:
            flash('Selected patient not found.', 'danger')
            return render_template('admin_appointment_form.html',patients=patients, doctors=doctors,next=return_url)
        if not doctor:
            flash('Selected doctor not found.', 'danger')
            return render_template('admin_appointment_form.html',patients=patients, doctors=doctors,next=return_url)
        
        # Conflict check: same doctor, same date & time, and not cancelled/deleted
        conflict = Appointment.query.filter_by(
            doctor_id=doctor_id,
            date=appt_date,
            time=appt_time
        ).filter(Appointment.status != 'Cancelled').first()

        if conflict:
            flash('Selected doctor already has an appointment at that date/time.', 'danger')
            return render_template('admin_appointment_form.html',patients=patients, doctors=doctors,next=return_url)
        # Create appointment
  
        try:
            appt = Appointment(patient_id=patient.id, doctor_id=doctor_id, date=appt_date, time=appt_time, status='Booked')
            db.session.add(appt)
            db.session.commit()
            flash(f"Appointment #{appt.id} booked successfully.", 'success')
            return redirect(url_for('main.admin_appointments') )
        except IntegrityError:
            db.session.rollback()
            flash('Failed to book. Possible conflict', 'danger')
            return redirect('admin_appointment_form.html',patients=patients, doctors=doctors)

    # GET -> render the form only. 
    return render_template('admin_appointment_form.html',patients=patients, doctors=doctors)

@main.route('/admin/appointment/<int:appt_id>/mark_completed', methods=['POST'])
@login_required
@role_required('admin')
@validate_csrf
def admin_mark_completed(appt_id):
 
    appt = get_appt_or_404(appt_id)

    if appt.status == 'Completed':
        flash('Appointment is already completed.', 'info')
        return redirect(url_for('main.admin_appointments'))

    appt.status = 'Completed'
    # optional: store who completed and when
    appt.completed_at = getattr(appt, 'completed_at', None) or datetime.utcnow()
    appt.completed_by = getattr(current_user, 'id', None)
    db.session.add(appt)
    db.session.commit()

    flash(f'Appointment #{appt.id} marked as Completed.', 'success')
    return redirect(url_for('main.admin_appointments') )


@main.route('/admin/appointment/<int:appt_id>/cancel', methods=['POST'])
@login_required
@role_required('admin')
@validate_csrf
def admin_cancel_appointment(appt_id):
  
    appt = get_appt_or_404(appt_id)

    if appt.status == 'Cancelled':
        flash('Appointment is already cancelled.', 'info')
        return redirect(url_for('main.admin_appointments') )
    # Mark cancelled
    appt.status = 'Cancelled'
    appt.cancelled_at = datetime.utcnow()
    appt.cancelled_by = getattr(current_user, 'id', None)
    # Optionally add a cancellation reason field if present:
    # appt.cancel_reason = request.form.get('reason')

    db.session.add(appt)
    db.session.commit()

    flash(f'Appointment #{appt.id} has been cancelled.', 'warning')
    return redirect(url_for('main.admin_appointments') )


@main.route('/admin/appointment/<int:appt_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
@validate_csrf
def admin_delete_appointment(appt_id):
    """
    POST endpoint to delete an appointment.
    Template posts to: url_for('main.admin_delete_appointment', appt_id=a.id)
    """
    appt = get_appt_or_404(appt_id)

    # Example: soft-delete if model has `deleted` boolean otherwise hard delete
    if hasattr(appt, 'deleted'):
        if appt.deleted:
            flash('Appointment already deleted.', 'info')
            return redirect(url_for('main.admin_appointments'))
        appt.deleted = True
        appt.deleted_at = datetime.utcnow()
        appt.deleted_by = getattr(current_user, 'id', None)
        db.session.add(appt)
    else:
        # no soft-delete field -> hard delete (be careful)
        db.session.delete(appt)

    db.session.commit()
    flash(f'Appointment #{appt_id} deleted.', 'danger')
    return redirect(url_for('main.admin_appointments'))

# ---------- DOCTOR ----------
@main.route('/doctor')
@login_required
@role_required('doctor')
def doctor_dashboard():

    LAST_N = 5  # number of recent past appointments to show
    doc = current_user.doctor
    if not doc:
        flash('Doctor profile missing', 'danger')
        return redirect(url_for('main.logout'))

    now = datetime.now()

    # Fetch all appointments for this doctor (ordered by date/time ascending)
    all_appts = (
        Appointment.query
        .filter_by(doctor_id=doc.id)
        .order_by(Appointment.date, Appointment.time)
        .all()
    )

    upcoming_appts = [
        a for a in all_appts
        if (a.date > now.date() or (a.date == now.date() and a.time >= now.time()))
           and a.status == 'Booked' 
    ]

    past_appts = [
        a for a in all_appts
        if (a.date < now.date() or (a.date == now.date() and a.time < now.time()) or a.status in ['Completed', 'Cancelled'])
    ]

    # Get last N past appointments (most recent first)
    past_appts_sorted_desc = sorted(past_appts, key=lambda x: (x.date, x.time), reverse=True)
    recent_appointments = past_appts_sorted_desc[:LAST_N]

    today = date.today()
    dates = [today + timedelta(days=i) for i in range(7)]

    rows = DoctorAvailability.query.filter(
        DoctorAvailability.doctor_id == doc.id,
        DoctorAvailability.date.in_(dates)
    ).all()
    rows_map = {r.date: r for r in rows}
    availability={}
    
    display_dates = [(d, d.isoformat(), d.strftime('%A %d %b %Y')) for d in dates]
    for d,k,v in display_dates:
        r = rows_map.get(d)
        if r:
            availability[k] = {'start': r.start_time.strftime('%H:%M'), 'end': r.end_time.strftime('%H:%M')}
   
    return render_template(
        'doctor_dashboard.html',
        doctor=doc,
        appointments=upcoming_appts,
        all_appointments=all_appts,
        recent_appointments=recent_appointments, 
        display_dates=display_dates,
        availability=availability
    )

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

TIME_RE = re.compile(r'^\d{2}:\d{2}$')

def valid_time_str(s):
    return bool(s and TIME_RE.match(s))

def parse_time(s):
    hh, mm = map(int, s.split(':'))
    return time(hh, mm)

@main.route('/doctor/availability', methods=['GET', 'POST'])
@login_required
@role_required('doctor')
@validate_csrf
def doctor_availability():
    doctor = DoctorProfile.query.filter_by(user_id=current_user.id).first()
    if not doctor:
        flash("Doctor profile not found.", "danger")
        return redirect(url_for('main.index'))

    today = date.today()
    dates = [today + timedelta(days=i) for i in range(7)]

    date_keys = [d.isoformat() for d in dates]  # "YYYY-MM-DD"

    if request.method == 'POST':
        # Clear all availability rows if requested
        if request.form.get("clear_all") == "1":
            try:
                db.session.query(DoctorAvailability).filter(
                    DoctorAvailability.doctor_id == doctor.id,
                    DoctorAvailability.date.in_(dates)
                ).delete(synchronize_session=False)
                db.session.commit()
                flash("Cleared availability for the next 7 days.", "info")
                return redirect(url_for('main.doctor_availability'))
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Failed to clear availability")
                flash("Failed to clear availability. Try again.", "danger")
                return redirect(url_for('main.doctor_availability'))

        # Otherwise, read fields for each day and upsert or delete
        errors = []
        try:
            for d in dates:
                key = d.isoformat()
                s = (request.form.get(f'{key}_start') or '').strip()
                e = (request.form.get(f'{key}_end') or '').strip()

                # If both empty => ensure deletion of any existing row for that date
                if not s and not e:
                    existing = DoctorAvailability.query.filter_by(doctor_id=doctor.id, date=d).first()
                    if existing:
                        db.session.delete(existing)
                    continue

                # validate times
                if not (valid_time_str(s) and valid_time_str(e)):
                    raise ValueError(f"Invalid time for {key}: use HH:MM (or leave empty).")

                start_t = parse_time(s)
                end_t = parse_time(e)
                if start_t >= end_t:
                    raise ValueError(f"For {d.strftime('%A %Y-%m-%d')}, start must be before end.")

                # upsert
                avail = DoctorAvailability.query.filter_by(doctor_id=doctor.id, date=d).first()
                if not avail:
                    avail = DoctorAvailability(doctor_id=doctor.id, date=d, start_time=start_t, end_time=end_t)
                    db.session.add(avail)
                else:
                    avail.start_time = start_t
                    avail.end_time = end_t
                    avail.updated_at = datetime.utcnow()

            db.session.commit()
            flash("Availability for next 7 days saved.", "success")
            return redirect(url_for('doctor.doctor_availability_next7'))

        except ValueError as ve:
            db.session.rollback()
            flash(str(ve), "danger")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to save daily availability")
            flash("Failed to save availability. Try again.", "danger")

    rows = DoctorAvailability.query.filter(
        DoctorAvailability.doctor_id == doctor.id,
        DoctorAvailability.date.in_(dates)
    ).all()
    rows_map = {r.date: r for r in rows}

    form_values = {}
    for d in dates:
        r = rows_map.get(d)
        form_values[f'{d.isoformat()}_start'] = r.start_time.strftime('%H:%M') if r else ''
        form_values[f'{d.isoformat()}_end'] = r.end_time.strftime('%H:%M') if r else ''

    display_dates = [(d, d.isoformat(), d.strftime('%A %d %b %Y')) for d in dates]

    return render_template('doctor_availability_single.html',
                           doctor=doctor,
                            display_dates=display_dates,
                            form_values=form_values
                           )
RESULTS_PER_PAGE = 10

@main.route('/doctors/search')
@login_required
def doctor_search():
 
    q = (request.args.get('q') or '').strip()
    specialty = (request.args.get('specialty') or '').strip()
    try:
        page = max(1, int(request.args.get('page', 1)))
    except ValueError:
        page = 1
    try:
        per_page = max(5, min(50, int(request.args.get('per_page', RESULTS_PER_PAGE))))
    except ValueError:
        per_page = RESULTS_PER_PAGE

    # Build base query
    query = DoctorProfile.query.options(joinedload(DoctorProfile.user))

    # Exclude blacklisted doctors by default (optional)
    query = query.filter(DoctorProfile.is_blacklisted == False)

    # Apply search filters
    if q:
        # search across user.name and user.email
        wildcard = f"%{q}%"
        # join to user via relationship attribute; SQLAlchemy will join for us via filter on related column
        query = query.join(DoctorProfile.user).filter(
            or_(
                User.name.ilike(wildcard),
                User.email.ilike(wildcard),
                DoctorProfile.specialization.ilike(wildcard)
            )
        )
    elif specialty:
        wildcard = f"%{specialty}%"
        query = query.filter(DoctorProfile.specialization.ilike(wildcard))

    # total count for pagination (runs a COUNT query)
    try:
        total = query.order_by(None).count()
    except Exception:
        current_app.logger.exception("Count failed for doctor search")
        total = 0

    # ordering: by name
    query = query.join(DoctorProfile.user).order_by(User.name.asc())

    # pagination
    offset = (page - 1) * per_page
    results = query.offset(offset).limit(per_page).all()

    # Prepare simple result summary for template
    pages = (total + per_page - 1) // per_page if total else 1
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': pages,
        'has_prev': page > 1,
        'has_next': page < pages,
        'prev_page': page - 1 if page > 1 else None,
        'next_page': page + 1 if page < pages else None,
    }

    # Render template
    return render_template(
        'doctor_search.html',
        results=results,
        q=q,
        specialty=specialty,
        pagination=pagination
    )
# ---------- PATIENT ----------
@main.route('/patient')
@login_required
@role_required('patient')
def patient_dashboard():
    
    # get patient profile for current_user
    patient = getattr(current_user, 'patient', None)
    if not patient:
        flash('Patient profile missing', 'danger')
        return redirect(url_for('main.logout'))

    # now and today for comparisons
    now_dt = datetime.now()
    today = now_dt.date()
    now_time = now_dt.time()
    total_count = db.session.query(func.count(Appointment.id)).filter(Appointment.patient_id == patient.id).scalar() or 0
    completed_count = db.session.query(func.count(Appointment.id)).filter(
        Appointment.patient_id == patient.id, Appointment.status == 'Completed').scalar() or 0
    cancelled_count = db.session.query(func.count(Appointment.id)).filter(
        Appointment.patient_id == patient.id, Appointment.status == 'Cancelled').scalar() or 0
    booked_count = db.session.query(func.count(Appointment.id)).filter(
        Appointment.patient_id == patient.id, Appointment.status == 'Booked').scalar() or 0

    upcoming_filter = and_(
        Appointment.patient_id == patient.id,
        Appointment.status != 'Cancelled',
        or_(
            Appointment.date > today,
            and_(Appointment.date == today, Appointment.time >= now_time)
        )
    )
    upcoming = (
        Appointment.query
        .options(
            joinedload(Appointment.doctor).joinedload(DoctorProfile.user)  # <- fixed
        )
        .filter(upcoming_filter)
        .order_by(Appointment.date.asc(), Appointment.time.asc())
        .all()
    )

    # Past appointments
    past_filter = and_(
        Appointment.patient_id == patient.id,
        or_(
            Appointment.date < today,
            and_(Appointment.date == today, Appointment.time < now_time)
        )
    )
    past = (
        Appointment.query
        .options(
            joinedload(Appointment.doctor).joinedload(DoctorProfile.user)  # <- fixed
        )
        .filter(past_filter)
        .order_by(Appointment.date.desc(), Appointment.time.desc())
        .all()
    )

    # ------- Last 5 past (already ordered desc) -------
    recent_appointments = past[:5]

    # ------- Departments (same data you were passing before) -------
    departments = Department.query.order_by(Department.name).all()

    return render_template(
        'patient_dashboard.html',
        patient=patient,
        upcoming=upcoming,
        past=past,
        recent_appointments=recent_appointments,
        all_appointments=None,
        departments=departments,
        total=total_count,
        completed=completed_count,
        cancelled=cancelled_count,
        booked=booked_count
    )

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
        return redirect(url_for('views.index'))

    if by == 'doctor':
        docs = DoctorProfile.query.join(User).filter(
            (User.name.ilike(f'%{q}%')) | (DoctorProfile.specialization.ilike(f'%{q}%'))
        ).all()
        return render_template('doctors_list.html', doctors=docs, q=q)
    else:
        pats = PatientProfile.query.join(User).filter(
            (User.name.ilike(f'%{q}%')) | (PatientProfile.contact.ilike(f'%{q}%'))
        ).all()
        return render_template('patients_list.html', patients=pats, q=q)

@main.route('/doctors')
@login_required
def list_all_doctors():
    docs = DoctorProfile.query.all()
    return render_template('doctors_list.html', doctors=docs)

@main.route('/doctors/<int:doctor_id>')
@login_required
def view_doctor(doctor_id):
    doc = DoctorProfile.query.get_or_404(doctor_id)
    return render_template('doctor_profile_view.html', doctor=doc)

@main.route('/patients')
@login_required
def list_all_patients():
    patient_list = PatientProfile.query.all()
    return render_template('patients_list.html', patients=patient_list)

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
    return redirect(url_for('views.index'))

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
