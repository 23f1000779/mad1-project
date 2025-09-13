from flask import Blueprint
from flask_restful import Api

api_bp = Blueprint('api', __name__, url_prefix='/api')
api = Api(api_bp)

from .resources import (
    DoctorListResource, DoctorResource,
    PatientListResource, PatientResource,
    AppointmentListResource, AppointmentResource
)

api.add_resource(DoctorListResource, '/doctors')
api.add_resource(DoctorResource, '/doctors/<int:doctor_id>')
api.add_resource(PatientListResource, '/patients')
api.add_resource(PatientResource, '/patients/<int:patient_id>')
api.add_resource(AppointmentListResource, '/appointments')
api.add_resource(AppointmentResource, '/appointments/<int:appointment_id>')
