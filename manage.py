from app import create_app, db
from app.models import User

app = create_app()

@app.cli.command("initdb")
def initdb():
    db.create_all()
    if not User.query.filter_by(email='admin@example.com').first():
        admin = User(email='admin@example.com', name='Administrator', role='admin')
        admin.set_password('AdminPass123')
        db.session.add(admin)
        db.session.commit()
        print('Created default admin: admin@example.com / AdminPass123')
    else:
        print('Admin already exists')

if __name__ == '__main__':
    app.run(debug=True)
