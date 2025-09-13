# Flask Hospital Project (with CSRF)

This is a minimal hospital management app using Flask + SQLite.

- Plain HTML forms (no Flask-WTF)
- CSRF implemented via session token (see `app/utils.py`)
- Blueprints: main routes and API (Flask-RESTful)
- Default admin created via `flask initdb`

### How to run

```bash
python -m venv venv
source venv/bin/activate   # (or venv\Scripts\activate on Windows)
pip install -r requirements.txt
export FLASK_APP=manage.py
flask initdb
flask run
