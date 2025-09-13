import os
from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'main.login'

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-secret')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hospital.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    login_manager.init_app(app)

    # Register blueprints (main and api)
    from .routes import main as main_bp
    from .api import api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    # CSRF token: ensure a token exists in session
    @app.before_request
    def ensure_csrf_token():
        from uuid import uuid4
        if 'csrf_token' not in session:
            session['csrf_token'] = uuid4().hex

    # Inject csrf_token into template context
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

    return app
