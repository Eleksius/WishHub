from app import app, db, User
from werkzeug.security import generate_password_hash
from datetime import date

app.app_context().push()
db.create_all()

admin = User(
    username="eleksius",
    password_hash=generate_password_hash("10Qpalzm$"),
    name="Алексей",
    is_admin=True,
    birthday=date(2009, 6, 9),
    emoji='😎'
)
user = User(
    username="zeero",
    password_hash=generate_password_hash("qwerty"),
    name="Денис",
    is_admin=False,
    birthday=date(2009, 6, 9),
    emoji='🔨'
)
db.session.add(admin)
db.session.add(user)
db.session.commit()
exit()