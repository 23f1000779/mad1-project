from . import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin/doctor/patient
    active = db.Column(db.Boolean, default=True)

    doctor = db.relationship('DoctorProfile', backref='user', uselist=False)
    patient = db.relationship('PatientProfile', backref='user', uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text)
    doctors_registered = db.Column(db.Integer, default=0)

class DoctorProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    specialization = db.Column(db.String(120))
    availability_json = db.Column(db.Text)
    bio = db.Column(db.Text)
    appointments = db.relationship('Appointment', backref='doctor', lazy='dynamic')

class PatientProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    contact = db.Column(db.String(40))
    dob = db.Column(db.Date)
    address = db.Column(db.Text)
    appointments = db.relationship('Appointment', backref='patient', lazy='dynamic')

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'))
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor_profile.id'))
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), default='Booked')  # Booked/Completed/Cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    treatment = db.relationship('Treatment', backref='appointment', uselist=False)

    __table_args__ = (
        db.UniqueConstraint('doctor_id', 'date', 'time', name='uix_doctor_datetime'),
    )

class Treatment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'))
    diagnosis = db.Column(db.Text)
    prescription = db.Column(db.Text)
    notes = db.Column(db.Text)
