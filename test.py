from app import app, db, User
from werkzeug.security import generate_password_hash
from datetime import date

app.app_context().push()
db.create_all()

admin = User(
    username="eleksius",
    password_hash=generate_password_hash("password"),
    name="Алексей",
    is_admin=True,
    birthday=date(2009, 6, 9),
    emoji='😎'
)
# user = User(
#     username="stesha",
#     password_hash=generate_password_hash("qwerty"),
#     name="Степанида",
#     is_admin=False,
#     birthday=date(1488, 6, 7),
#     emoji='😺'
# )
db.session.add(admin)
# db.session.add(user)
db.session.commit()
exit()