from . import db
from .models import User, DoctorProfile, PatientProfile, Appointment, Department, Treatment

class userRepository:

    def get_by_email(self,email):
        return User.query.filter_by(email=email).first()


    def create(self, email, name, password, role):
        user = User(email=email, name=name, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user

    def get_by_id(self,user_id):
        return User.query.get(user_id)

    def get_list(self, offset=0, limit=50):
        return User.query.offset(offset).limit(limit).all()

    def get_list_by_role(self, role, offset=0, limit=50):
        return User.query.filter_by(role=role).offset(offset).limit(limit).all()
    def deactivate_user(self, user_id, reason):
        user = self.get_by_id(user_id)
        if user:
            user.active = False
            user.reason = reason
            db.session.commit()
        return user
    def activate_user(self, user_id):
        user = self.get_by_id(user_id)
        if user:
            user.active = True
            user.reason = None
            db.session.commit()
        return user
class departmentRepository:

    def get_by_id(self, department_id):
        return Department.query.get(department_id)

    def create(self, name, description):
        department = Department(name=name, description=description)
        db.session.add(department)
        db.session.commit()
        return department

    def get_list(self, offset=0, limit=50):
        return Department.query.offset(offset).limit(limit).all()

class doctorProfileRepository:

    def get_by_user_id(self, user_id):
        return DoctorProfile.query.filter_by(user_id=user_id).first()

    def create(self, user_id, specialization, availability_json, bio):
        profile = DoctorProfile(user_id=user_id, specialization=specialization,
                                availability_json=availability_json, bio=bio)
        db.session.add(profile)
        db.session.commit()
        return profile

    def get_list(self, offset=0, limit=50):
        return DoctorProfile.query.offset(offset).limit(limit).all()
 
class patientProfileRepository:

    def get_by_user_id(self, user_id):
        return PatientProfile.query.filter_by(user_id=user_id).first()

    def create(self, user_id, contact, dob, address):
        profile = PatientProfile(user_id=user_id, contact=contact, dob=dob, address=address)
        db.session.add(profile)
        db.session.commit()
        return profile

    def get_list(self, offset=0, limit=50):
        return PatientProfile.query.offset(offset).limit(limit).all()
class appointmentRepository:

    def get_by_id(self, appointment_id):
        return Appointment.query.get(appointment_id)

    def create(self, patient_id, doctor_id, date, time):
        appointment = Appointment(patient_id=patient_id, doctor_id=doctor_id, date=date, time=time)
        db.session.add(appointment)
        db.session.commit()
        return appointment

    def get_list(self, offset=0, limit=50):
        return Appointment.query.offset(offset).limit(limit).all()

    def get_by_doctor_and_datetime(self, doctor_id, date, time):
        return Appointment.query.filter_by(doctor_id=doctor_id, date=date, time=time).first()
    def get_by_patient(self, patient_id, offset=0, limit=50):
        return Appointment.query.filter_by(patient_id=patient_id).offset(offset).limit(limit).all()
    def get_by_doctor(self, doctor_id, offset=0, limit=50):
        return Appointment.query.filter_by(doctor_id=doctor_id).offset(offset).limit(limit).all()
    def update_status(self, appointment_id, status):
        appointment = self.get_by_id(appointment_id)
        if appointment:
            appointment.status = status
            db.session.commit()
        return appointment
class treatmentRepository:

    def get_by_id(self, treatment_id):
        return Treatment.query.get(treatment_id)

    def create(self, appointment_id, details):
        treatment = Treatment(appointment_id=appointment_id, details=details)
        db.session.add(treatment)
        db.session.commit()
        return treatment

    def get_list(self, offset=0, limit=50):
        return Treatment.query.offset(offset).limit(limit).all()
    def get_by_appointment(self, appointment_id):
        return Treatment.query.filter_by(appointment_id=appointment_id).first()
    def update_details(self, treatment_id, details):
        treatment = self.get_by_id(treatment_id)
        if treatment:
            treatment.details = details
            db.session.commit()
        return treatment
    def delete(self, treatment_id):
        treatment = self.get_by_id(treatment_id)
        if treatment:
            db.session.delete(treatment)
            db.session.commit()
        return treatment

