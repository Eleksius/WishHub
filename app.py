from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-family-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wishhub.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# --- МОДЕЛИ БАЗЫ ДАННЫХ ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    birthday = db.Column(db.Date, nullable=True)
    wishes = db.relationship('WishItem', backref='owner', lazy=True, foreign_keys='WishItem.user_id')


class WishItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    link = db.Column(db.String(255), nullable=True)
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    booked_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_purchased = db.Column(db.Boolean, default=False)

    booked_by = db.relationship('User', foreign_keys=[booked_by_id])


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- ЛОГИКА СОБЫТИЙ ---
def get_upcoming_events():
    today = date.today()
    events = []

    users = User.query.all()
    for user in users:
        if user.birthday:
            bday_this_year = date(today.year, user.birthday.month, user.birthday.day)
            delta = (bday_this_year - today).days
            if delta < 0:
                bday_this_year = date(today.year + 1, user.birthday.month, user.birthday.day)
                delta = (bday_this_year - today).days
            if 0 <= delta <= 30:
                # ПРАВКА 1: Убрали слово "близкого"
                events.append({
                    'text': f"День рождения у человека: {user.name}",
                    'date': bday_this_year.strftime('%d.%m'),
                    'days_left': delta,
                    'icon': 'bi-balloon-heart'
                })

    holidays = [
        ("Новый год", 12, 31, "bi-tree"),
        ("23 Февраля", 2, 23, "bi-shield-check"),
        ("8 Марта", 3, 8, "bi-flower1")
    ]
    for name, month, day, icon in holidays:
        holiday_date = date(today.year, month, day)
        if holiday_date < today:
            holiday_date = date(today.year + 1, month, day)
        delta = (holiday_date - today).days
        if 0 <= delta <= 30:
            events.append({
                'text': name,
                'date': holiday_date.strftime('%d.%m'),
                'days_left': delta,
                'icon': icon
            })

    return sorted(events, key=lambda x: x['days_left'])


# --- МАРШРУТЫ ---
@app.route('/')
@login_required
def index():
    users = User.query.filter(User.id != current_user.id).all()
    events = get_upcoming_events()
    return render_template('index.html', users=users, events=events)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            login_user(user)
            return redirect(url_for('index'))
        flash('Неверный логин или пароль', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/my_wishlist', methods=['GET', 'POST'])
@login_required
def my_wishlist():
    if request.method == 'POST':
        new_wish = WishItem(
            title=request.form['title'],
            description=request.form['description'],
            link=request.form['link'],
            priority=request.form.get('priority', 'medium'),
            user_id=current_user.id
        )
        db.session.add(new_wish)
        db.session.commit()
        flash('Желание успешно добавлено!', 'success')
        return redirect(url_for('my_wishlist'))

    wishes = WishItem.query.filter_by(user_id=current_user.id).all()
    return render_template('my_wishlist.html', wishes=wishes)


@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    new_username = request.form['username'].strip()
    new_name = request.form['name'].strip()
    new_birthday = request.form['birthday']
    new_password = request.form['password'].strip()

    existing_user = User.query.filter_by(username=new_username).first()
    if existing_user and existing_user.id != current_user.id:
        flash('Этот логин уже занят другим членом семьи!', 'danger')
        return redirect(url_for('my_wishlist'))

    current_user.username = new_username
    current_user.name = new_name

    if new_birthday:
        current_user.birthday = datetime.strptime(new_birthday, '%Y-%m-%d').date()
    else:
        current_user.birthday = None

    if new_password:
        current_user.password_hash = generate_password_hash(new_password)

    db.session.commit()
    flash('Профиль успешно обновлен!', 'success')
    return redirect(url_for('my_wishlist'))


# ПРАВКА 2: Создание пользователей админом прямо с сайта
@app.route('/create_user', methods=['POST'])
@login_required
def create_user():
    if not current_user.is_admin:
        flash('У вас нет прав для этого действия!', 'danger')
        return redirect(url_for('index'))

    username = request.form['username'].strip()
    name = request.form['name'].strip()
    password = request.form['password'].strip()
    birthday_str = request.form['birthday']
    is_admin = 'is_admin' in request.form

    if User.query.filter_by(username=username).first():
        flash('Пользователь с таким логином уже существует!', 'danger')
        return redirect(url_for('my_wishlist'))

    birthday = datetime.strptime(birthday_str, '%Y-%m-%d').date() if birthday_str else None

    new_user = User(
        username=username,
        name=name,
        password_hash=generate_password_hash(password),
        birthday=birthday,
        is_admin=is_admin
    )
    db.session.add(new_user)
    db.session.commit()

    flash(f'Пользователь {name} успешно добавлен в семейный круг!', 'success')
    return redirect(url_for('my_wishlist'))


@app.route('/delete_wish/<int:item_id>')
@login_required
def delete_wish(item_id):
    item = WishItem.query.get_or_404(item_id)
    if item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
        flash('Желание удалено.', 'info')
    return redirect(url_for('my_wishlist'))


@app.route('/user/<int:user_id>')
@login_required
def view_wishlist(user_id):
    if user_id == current_user.id:
        return redirect(url_for('my_wishlist'))

    target_user = User.query.get_or_404(user_id)
    wishes = WishItem.query.filter_by(user_id=user_id).all()
    return render_template('wishlist.html', target_user=target_user, wishes=wishes)


@app.route('/book/<int:item_id>')
@login_required
def book_item(item_id):
    item = WishItem.query.get_or_404(item_id)
    if item.user_id != current_user.id and not item.booked_by_id:
        item.booked_by_id = current_user.id
        db.session.commit()
        flash('Вы забронировали этот подарок!', 'success')
    return redirect(url_for('view_wishlist', user_id=item.user_id))


@app.route('/unbook/<int:item_id>')
@login_required
def unbook_item(item_id):
    item = WishItem.query.get_or_404(item_id)
    if item.booked_by_id == current_user.id:
        item.booked_by_id = None
        db.session.commit()
        flash('Бронь отменена.', 'info')
    return redirect(url_for('view_wishlist', user_id=item.user_id))


@app.route('/purchase/<int:item_id>')
@login_required
def purchase_item(item_id):
    item = WishItem.query.get_or_404(item_id)
    if item.booked_by_id == current_user.id:
        item.is_purchased = True
        db.session.commit()
        flash('Подарок отмечен как врученный! Интрига раскрыта.', 'success')
    return redirect(url_for('view_wishlist', user_id=item.user_id))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)