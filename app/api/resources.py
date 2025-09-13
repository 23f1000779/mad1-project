from flask_restful import Resource, reqparse, fields, marshal_with, abort
from flask import request
from ..models import db, DoctorProfile, PatientProfile, Appointment, User
from datetime import datetime

doctor_fields = {
    'id': fields.Integer,
    'name': fields.String(attribute=lambda d: d.user.name if d.user else ''),
    'specialization': fields.String
}

patient_fields = {
    'id': fields.Integer,
    'name': fields.String(attribute=lambda p: p.user.name if p.user else ''),
    'contact': fields.String
}

appointment_fields = {
    'id': fields.Integer,
    'patient_id': fields.Integer,
    'doctor_id': fields.Integer,
    'date': fields.String,
    'time': fields.String,
    'status': fields.String
}

doctor_parser = reqparse.RequestParser()
doctor_parser.add_argument('name', type=str, required=True)
doctor_parser.add_argument('email', type=str, required=True)
doctor_parser.add_argument('specialization', type=str)

patient_parser = reqparse.RequestParser()
patient_parser.add_argument('name', type=str, required=True)
patient_parser.add_argument('email', type=str, required=True)
patient_parser.add_argument('contact', type=str)

appointment_parser = reqparse.RequestParser()
appointment_parser.add_argument('patient_id', type=int, required=True)
appointment_parser.add_argument('doctor_id', type=int, required=True)
appointment_parser.add_argument('date', type=lambda x: datetime.strptime(x, '%Y-%m-%d').date(), required=True)
appointment_parser.add_argument('time', type=lambda x: datetime.strptime(x, '%H:%M').time(), required=True)
appointment_parser.add_argument('status', type=str, default='Booked')

class DoctorListResource(Resource):
    @marshal_with(doctor_fields)
    def get(self):
        return DoctorProfile.query.all(), 200

    def post(self):
        args = doctor_parser.parse_args()
        if User.query.filter_by(email=args['email']).first():
            abort(400, message='Email already exists')
        user = User(email=args['email'], name=args['name'], role='doctor')
        user.set_password('Doctor@123')
        db.session.add(user)
        db.session.commit()
        doc = DoctorProfile(user_id=user.id, specialization=args.get('specialization'))
        db.session.add(doc)
        db.session.commit()
        return {'id': doc.id}, 201

class DoctorResource(Resource):
    @marshal_with(doctor_fields)
    def get(self, doctor_id):
        return DoctorProfile.query.get_or_404(doctor_id), 200

    def put(self, doctor_id):
        args = doctor_parser.parse_args()
        doc = DoctorProfile.query.get_or_404(doctor_id)
        doc.user.name = args['name']
        doc.specialization = args.get('specialization')
        db.session.commit()
        return {'message': 'Updated'}, 200

    def delete(self, doctor_id):
        doc = DoctorProfile.query.get_or_404(doctor_id)
        doc.user.active = False
        db.session.commit()
        return {'message': 'Deactivated'}, 200

class PatientListResource(Resource):
    @marshal_with(patient_fields)
    def get(self):
        return PatientProfile.query.all(), 200

    def post(self):
        args = patient_parser.parse_args()
        if User.query.filter_by(email=args['email']).first():
            abort(400, message='Email already exists')
        user = User(email=args['email'], name=args['name'], role='patient')
        user.set_password('Patient@123')
        db.session.add(user)
        db.session.commit()
        pat = PatientProfile(user_id=user.id, contact=args.get('contact'))
        db.session.add(pat)
        db.session.commit()
        return {'id': pat.id}, 201

class PatientResource(Resource):
    @marshal_with(patient_fields)
    def get(self, patient_id):
        return PatientProfile.query.get_or_404(patient_id), 200

    def put(self, patient_id):
        args = patient_parser.parse_args()
        pat = PatientProfile.query.get_or_404(patient_id)
        pat.user.name = args['name']
        pat.contact = args.get('contact')
        db.session.commit()
        return {'message': 'Updated'}, 200

    def delete(self, patient_id):
        pat = PatientProfile.query.get_or_404(patient_id)
        pat.user.active = False
        db.session.commit()
        return {'message': 'Deactivated'}, 200

class AppointmentListResource(Resource):
    @marshal_with(appointment_fields)
    def get(self):
        doctor_id = request.args.get('doctor_id', type=int)
        patient_id = request.args.get('patient_id', type=int)
        date_str = request.args.get('date')
        q = Appointment.query
        if doctor_id:
            q = q.filter_by(doctor_id=doctor_id)
        if patient_id:
            q = q.filter_by(patient_id=patient_id)
        if date_str:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
            q = q.filter_by(date=d)
        return q.all(), 200

    def post(self):
        args = appointment_parser.parse_args()
        conflict = Appointment.query.filter_by(doctor_id=args['doctor_id'], date=args['date'], time=args['time']).first()
        if conflict:
            abort(400, message='Doctor already has appointment at that date/time')
        appt = Appointment(patient_id=args['patient_id'], doctor_id=args['doctor_id'], date=args['date'], time=args['time'], status=args['status'])
        db.session.add(appt)
        db.session.commit()
        return {'id': appt.id}, 201

class AppointmentResource(Resource):
    @marshal_with(appointment_fields)
    def get(self, appointment_id):
        return Appointment.query.get_or_404(appointment_id), 200

    def put(self, appointment_id):
        args = appointment_parser.parse_args()
        appt = Appointment.query.get_or_404(appointment_id)
        if (appt.doctor_id != args['doctor_id']) or (appt.date != args['date']) or (appt.time != args['time']):
            conflict = Appointment.query.filter_by(doctor_id=args['doctor_id'], date=args['date'], time=args['time']).first()
            if conflict and conflict.id != appt.id:
                abort(400, message='Conflict with another appointment')
        appt.patient_id = args['patient_id']
        appt.doctor_id = args['doctor_id']
        appt.date = args['date']
        appt.time = args['time']
        appt.status = args.get('status')
        db.session.commit()
        return {'message': 'Updated'}, 200

    def delete(self, appointment_id):
        appt = Appointment.query.get_or_404(appointment_id)
        appt.status = 'Cancelled'
        db.session.commit()
        return {'message': 'Cancelled'}, 200
