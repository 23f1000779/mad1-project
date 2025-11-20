from functools import wraps
from flask import session, request, flash, redirect, url_for

def validate_csrf(func):
    """
    Decorator to validate CSRF token for POST endpoints.
    Checks form field 'csrf_token' or header 'X-CSRF-Token'.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        token = session.get('csrf_token')
        form_token = None
        if request.method == 'POST':
            form_token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
        if request.method == 'POST':
            if not token or not form_token or token != form_token:
                flash('Invalid or missing CSRF token', 'danger')
                return redirect(url_for('views.index'))
        return func(*args, **kwargs)
    return wrapper
