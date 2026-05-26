from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import os

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

app = Flask(__name__)
# SECRET_KEY из переменной окружения — не хранить в коде!
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-me-in-production-please')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

if os.path.exists('/data'):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////data/wishhub.db'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wishhub.db'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

EMOJIS = ['🎁','🍕','🐱','🎮','🏀','🚀','⭐','🦖','🍿','💡','🍩','🦊','🥑','🎸','🌸','🦋','🐶','🦁','🐉','🌈','🐸','🌺','🦄','🍓']

CATEGORIES = [
    ('tech',    '🖥️', 'Техника',      'linear-gradient(135deg,#1e40af,#3b82f6)'),
    ('clothes', '👗', 'Одежда',       'linear-gradient(135deg,#9d174d,#ec4899)'),
    ('books',   '📚', 'Книги',        'linear-gradient(135deg,#92400e,#f97316)'),
    ('games',   '🎮', 'Игры',         'linear-gradient(135deg,#4c1d95,#8b5cf6)'),
    ('food',    '🍕', 'Еда и напитки','linear-gradient(135deg,#7f1d1d,#ef4444)'),
    ('travel',  '✈️', 'Путешествия',  'linear-gradient(135deg,#155e75,#06b6d4)'),
    ('sport',   '⚽', 'Спорт',        'linear-gradient(135deg,#14532d,#22c55e)'),
    ('beauty',  '💄', 'Красота',      'linear-gradient(135deg,#701a75,#e879f9)'),
    ('home',    '🏠', 'Дом',          'linear-gradient(135deg,#78350f,#f59e0b)'),
    ('other',   '🎁', 'Другое',       'linear-gradient(135deg,#334155,#94a3b8)'),
]
CATEGORY_MAP = {c[0]: {'emoji': c[1], 'label': c[2], 'gradient': c[3]} for c in CATEGORIES}

EVENT_ICONS = [
    ('bi-balloon-heart-fill','🎈 Праздник'),('bi-tree','🎄 Новый год'),('bi-heart-fill','❤️ День влюблённых'),
    ('bi-star-fill','⭐ Особый день'),('bi-house-heart','🏠 Домашний'),('bi-gift-fill','🎁 Подарок'),
    ('bi-music-note-beamed','🎵 Музыка'),('bi-sun-fill','☀️ Лето'),
]

# ──── МОДЕЛИ ────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name          = db.Column(db.String(50), nullable=False)
    is_admin      = db.Column(db.Boolean, default=False)
    birthday      = db.Column(db.Date, nullable=True)
    emoji         = db.Column(db.String(10), default='🎁')
    wishes        = db.relationship('WishItem', backref='owner', lazy=True, foreign_keys='WishItem.user_id')

class WishItem(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    title        = db.Column(db.String(100), nullable=False)
    description  = db.Column(db.Text, nullable=True)
    link         = db.Column(db.String(500), nullable=True)
    image_url    = db.Column(db.String(500), nullable=True)
    price        = db.Column(db.Float, nullable=True)
    category     = db.Column(db.String(20), default='other')
    priority     = db.Column(db.String(20), default='medium')
    user_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    booked_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_purchased = db.Column(db.Boolean, default=False)
    purchased_at = db.Column(db.DateTime, nullable=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    booked_by    = db.relationship('User', foreign_keys=[booked_by_id])

class Comment(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    wish_id    = db.Column(db.Integer, db.ForeignKey('wish_item.id', ondelete='CASCADE'), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text       = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author     = db.relationship('User', foreign_keys=[user_id])
    wish       = db.relationship('WishItem', backref=db.backref('comments', lazy=True, cascade='all,delete-orphan'))

class FamilyEvent(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(100), nullable=False)
    month          = db.Column(db.Integer, nullable=False)
    day            = db.Column(db.Integer, nullable=False)
    icon           = db.Column(db.String(50), default='bi-star-fill')
    created_by_id  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ──── HELPERS ───────────────────────────────────────────────────────────────

def get_upcoming_events():
    today = date.today()
    events = []
    for user in User.query.all():
        if not user.birthday:
            continue
        try:
            bday = date(today.year, user.birthday.month, user.birthday.day)
        except ValueError:
            continue
        delta = (bday - today).days
        if delta < 0:
            bday = date(today.year + 1, user.birthday.month, user.birthday.day)
            delta = (bday - today).days
        if 0 <= delta <= 30:
            events.append({'text': f'День рождения: {user.name}', 'date': bday.strftime('%d.%m'),
                           'days_left': delta, 'icon': 'bi-balloon-heart-fill',
                           'type': 'birthday', 'user_id': user.id})
    fixed = [
        ('Новый год 🎄', 1, 1, 'bi-tree'), ('23 Февраля', 2, 23, 'bi-shield-check'),
        ('8 Марта', 3, 8, 'bi-flower1'), ('День Победы', 5, 9, 'bi-star'),
        ('Новый год 🎄', 12, 31, 'bi-tree'),
    ]
    for name, month, day, icon in fixed:
        try:
            hday = date(today.year, month, day)
        except ValueError:
            continue
        if hday < today:
            hday = date(today.year + 1, month, day)
        delta = (hday - today).days
        if 0 <= delta <= 30:
            events.append({'text': name, 'date': hday.strftime('%d.%m'), 'days_left': delta, 'icon': icon, 'type': 'holiday'})
    for ev in FamilyEvent.query.all():
        try:
            eday = date(today.year, ev.month, ev.day)
        except ValueError:
            continue
        if eday < today:
            eday = date(today.year + 1, ev.month, ev.day)
        delta = (eday - today).days
        if 0 <= delta <= 30:
            events.append({'text': ev.name, 'date': eday.strftime('%d.%m'), 'days_left': delta,
                           'icon': ev.icon, 'type': 'custom', 'event_id': ev.id})
    return sorted(events, key=lambda x: x['days_left'])

def fetch_og_image(url):
    if not url or not HAS_REQUESTS:
        return None
    try:
        resp = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0 WishHub/1.0'})
        soup = BeautifulSoup(resp.text, 'html.parser')
        for attr in [('property', 'og:image'), ('name', 'og:image'), ('property', 'twitter:image')]:
            tag = soup.find('meta', {attr[0]: attr[1]})
            if tag and tag.get('content'):
                return tag['content']
    except Exception:
        pass
    return None

# ──── МАРШРУТЫ ──────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    users = User.query.filter(User.id != current_user.id).all()
    events = get_upcoming_events()
    stats = {}
    for u in users:
        total   = WishItem.query.filter_by(user_id=u.id, is_purchased=False).count()
        booked  = WishItem.query.filter_by(user_id=u.id, is_purchased=False).filter(WishItem.booked_by_id != None).count()
        stats[u.id] = {'total': total, 'booked': booked}
    return render_template('index.html', users=users, events=events, stats=stats)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username', '').strip()).first()
        if user and check_password_hash(user.password_hash, request.form.get('password', '')):
            login_user(user)
            return redirect(url_for('index'))
        flash('Неверный логин или пароль', 'danger')
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/my_wishlist', methods=['GET', 'POST'])
@login_required
def my_wishlist():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()[:100]
        if not title:
            flash('Название обязательно!', 'danger')
            return redirect(url_for('my_wishlist'))
        link      = request.form.get('link', '').strip()[:500]
        image_url = request.form.get('image_url', '').strip()[:500]
        if link and not image_url:
            image_url = fetch_og_image(link) or ''
        price = None
        price_str = request.form.get('price', '').strip().replace(',', '.').replace(' ', '')
        if price_str:
            try:
                price = float(price_str)
            except ValueError:
                pass
        wish = WishItem(
            title=title,
            description=request.form.get('description', '').strip()[:1000],
            link=link, image_url=image_url, price=price,
            category=request.form.get('category', 'other'),
            priority=request.form.get('priority', 'medium'),
            user_id=current_user.id,
        )
        db.session.add(wish)
        db.session.commit()
        flash('Желание добавлено! ✨', 'success')
        return redirect(url_for('my_wishlist'))
    wishes = WishItem.query.filter_by(user_id=current_user.id).order_by(WishItem.created_at.desc()).all()
    family_events = FamilyEvent.query.all()
    return render_template('my_wishlist.html', wishes=wishes, emojis=EMOJIS,
                           categories=CATEGORIES, category_map=CATEGORY_MAP,
                           family_events=family_events, event_icons=EVENT_ICONS)

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    new_username = request.form.get('username', '').strip()[:50]
    new_name     = request.form.get('name', '').strip()[:50]
    if not new_username or not new_name:
        flash('Имя и логин обязательны!', 'danger')
        return redirect(url_for('my_wishlist'))
    existing = User.query.filter_by(username=new_username).first()
    if existing and existing.id != current_user.id:
        flash('Этот логин уже занят!', 'danger')
        return redirect(url_for('my_wishlist'))
    current_user.username = new_username
    current_user.name     = new_name
    current_user.emoji    = request.form.get('emoji', '🎁')
    birthday_str = request.form.get('birthday', '')
    if birthday_str:
        try:
            current_user.birthday = datetime.strptime(birthday_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    else:
        current_user.birthday = None
    pw = request.form.get('password', '').strip()
    if pw and len(pw) >= 4:
        current_user.password_hash = generate_password_hash(pw)
    db.session.commit()
    flash('Профиль обновлён! 🎉', 'success')
    return redirect(url_for('my_wishlist'))

@app.route('/create_user', methods=['POST'])
@login_required
def create_user():
    if not current_user.is_admin:
        abort(403)
    username = request.form.get('username', '').strip()[:50]
    name     = request.form.get('name', '').strip()[:50]
    password = request.form.get('password', '').strip()
    if not all([username, name, password]):
        flash('Заполни все поля!', 'danger')
        return redirect(url_for('my_wishlist'))
    if User.query.filter_by(username=username).first():
        flash('Такой логин уже существует!', 'danger')
        return redirect(url_for('my_wishlist'))
    birthday = None
    bd_str = request.form.get('birthday', '')
    if bd_str:
        try:
            birthday = datetime.strptime(bd_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    new_user = User(username=username, name=name,
                    password_hash=generate_password_hash(password),
                    birthday=birthday, is_admin='is_admin' in request.form,
                    emoji=request.form.get('emoji', '🎁'))
    db.session.add(new_user)
    db.session.commit()
    flash(f'{name} добавлен в семейный круг! 🎉', 'success')
    return redirect(url_for('my_wishlist'))

@app.route('/delete_wish/<int:item_id>', methods=['POST'])
@login_required
def delete_wish(item_id):
    item = db.session.get(WishItem, item_id)
    if item and item.user_id == current_user.id and not item.booked_by_id:
        db.session.delete(item)
        db.session.commit()
        flash('Желание удалено.', 'info')
    elif item and item.booked_by_id:
        flash('Нельзя удалить — кто-то уже бронирует этот подарок! 🎁', 'warning')
    return redirect(url_for('my_wishlist'))

@app.route('/user/<int:user_id>')
@login_required
def view_wishlist(user_id):
    if user_id == current_user.id:
        return redirect(url_for('my_wishlist'))
    target_user = db.session.get(User, user_id)
    if not target_user:
        abort(404)
    wishes = WishItem.query.filter_by(user_id=user_id, is_purchased=False)\
                           .order_by(WishItem.created_at.desc()).all()
    return render_template('wishlist.html', target_user=target_user, wishes=wishes,
                           category_map=CATEGORY_MAP, categories=CATEGORIES)

@app.route('/book/<int:item_id>', methods=['POST'])
@login_required
def book_item(item_id):
    item = db.session.get(WishItem, item_id)
    if not item:
        abort(404)
    if item.user_id != current_user.id and not item.booked_by_id and not item.is_purchased:
        item.booked_by_id = current_user.id
        db.session.commit()
        flash(f'Ты забронировал «{item.title}»! 🎁', 'success')
    return redirect(url_for('view_wishlist', user_id=item.user_id))

@app.route('/unbook/<int:item_id>', methods=['POST'])
@login_required
def unbook_item(item_id):
    item = db.session.get(WishItem, item_id)
    if not item:
        abort(404)
    if item.booked_by_id == current_user.id:
        item.booked_by_id = None
        db.session.commit()
        flash('Бронь отменена.', 'info')
    return redirect(url_for('view_wishlist', user_id=item.user_id))

@app.route('/purchase/<int:item_id>', methods=['POST'])
@login_required
def purchase_item(item_id):
    item = db.session.get(WishItem, item_id)
    if not item:
        abort(404)
    if item.booked_by_id == current_user.id:
        item.is_purchased = True
        item.purchased_at = datetime.utcnow()
        db.session.commit()
        flash(f'🎉 Подарок «{item.title}» вручён! Ты лучший!', 'success')
    return redirect(url_for('view_wishlist', user_id=item.user_id))

@app.route('/comment/<int:item_id>', methods=['POST'])
@login_required
def add_comment(item_id):
    item = db.session.get(WishItem, item_id)
    if not item or item.user_id == current_user.id:
        abort(403)
    text = request.form.get('text', '').strip()[:500]
    if text:
        db.session.add(Comment(wish_id=item_id, user_id=current_user.id, text=text))
        db.session.commit()
    return redirect(url_for('view_wishlist', user_id=item.user_id) + f'#wish-{item_id}')

@app.route('/history')
@login_required
def history():
    purchased = WishItem.query.filter_by(is_purchased=True)\
                              .order_by(WishItem.purchased_at.desc()).all()
    return render_template('history.html', purchased=purchased, category_map=CATEGORY_MAP)

@app.route('/add_event', methods=['POST'])
@login_required
def add_event():
    name  = request.form.get('name', '').strip()[:100]
    month = request.form.get('month', '1')
    day   = request.form.get('day', '1')
    icon  = request.form.get('icon', 'bi-star-fill')
    try:
        month, day = int(month), int(day)
        date(2024, month, day)  # validate
        if name:
            db.session.add(FamilyEvent(name=name, month=month, day=day, icon=icon, created_by_id=current_user.id))
            db.session.commit()
            flash(f'Событие «{name}» добавлено! 🗓️', 'success')
    except ValueError:
        flash('Неверная дата!', 'danger')
    return redirect(url_for('my_wishlist'))

@app.route('/delete_event/<int:event_id>', methods=['POST'])
@login_required
def delete_event(event_id):
    ev = db.session.get(FamilyEvent, event_id)
    if ev and (ev.created_by_id == current_user.id or current_user.is_admin):
        db.session.delete(ev)
        db.session.commit()
    return redirect(url_for('my_wishlist'))

@app.route('/api/fetch_preview', methods=['POST'])
@login_required
def fetch_preview():
    url = (request.json or {}).get('url', '')
    img = fetch_og_image(url)
    return jsonify({'image_url': img or ''})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 80))
    app.run(host='0.0.0.0', port=port)
