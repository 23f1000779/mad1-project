import os
from os import path
from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from .constants import APP_NAME, APP_VERSION, DB_NAME, DEFAULT_ADMIN, DEFAULT_PASS


db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'views.login'  
def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'TheGodMustBeCrazy123!#')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    login_manager.init_app(app)

    # Register blueprints (views, main and api)
    from .views import views as views_bp
    from .routes import main as main_bp
    from .api import api_bp


    app.register_blueprint(views_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    # Global constants into template context which shall be used in base.html
    @app.context_processor
    def inject_globals():
        return {
            "APP_NAME": APP_NAME,
            "APP_VERSION": APP_VERSION
        }

    # CSRF token: token to be used for CSRF protection in forms
    @app.before_request
    def ensure_csrf_token():
        from uuid import uuid4
        if 'csrf_token' not in session:
            session['csrf_token'] = uuid4().hex

    # Push CSRF token to templates
    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=session.get('csrf_token'))

    # User loader for Flask-Login
    from .models import User
    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except Exception:
            return None

    create_database(app)
    return app


def create_database(app):
    if not path.exists(DB_NAME):
        with app.app_context():  # Ensure we are in the app context to create the database
            db.create_all()
            from .models import User
            if not User.query.filter_by(email=DEFAULT_ADMIN).first():
                user = User(email=DEFAULT_ADMIN, name='Administrator', role='admin')
                user.set_password(DEFAULT_PASS)
                
                db.session.add(user)
                db.session.commit()
                
                print(f'Created default admin: {{DEFAULT_ADMIN}} / {{DEFAULT_PASS}}')
            else:
                print('Admin already exists')
