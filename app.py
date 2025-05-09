from flask import Flask, render_template, redirect, request, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Modelos
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(100))
    links = db.relationship('Link', backref='owner', lazy=True)

class Link(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_url = db.Column(db.String(500))
    custom_slug = db.Column(db.String(100), unique=True)
    clicks = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Rotas
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']
    
    if User.query.filter_by(username=username).first():
        flash('Username already exists')
        return redirect(url_for('index'))
    
    new_user = User(username=username, password=password)
    db.session.add(new_user)
    db.session.commit()
    
    login_user(new_user)
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    user = User.query.filter_by(username=username).first()
    
    if user and user.password == password:
        login_user(user)
        return redirect(url_for('dashboard'))
    
    flash('Invalid credentials')
    return redirect(url_for('index'))

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        original_url = request.form['url']
        custom_slug = request.form['slug']
        
        if Link.query.filter_by(custom_slug=custom_slug).first():
            flash('Slug already in use')
            return redirect(url_for('dashboard'))
        
        new_link = Link(
            original_url=original_url,
            custom_slug=custom_slug,
            owner=current_user
        )
        db.session.add(new_link)
        db.session.commit()
        flash('Link created successfully!')
    
    user_links = Link.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', links=user_links)

@app.route('/<slug>')
def redirect_link(slug):
    link = Link.query.filter_by(custom_slug=slug).first()
    if link:
        link.clicks += 1
        db.session.commit()
        return redirect(link.original_url)
    return 'Link not found', 404

@app.route('/stats/<slug>')
@login_required
def stats(slug):
    link = Link.query.filter_by(custom_slug=slug).first()
    if link and link.owner.id == current_user.id:
        return render_template('stats.html', link=link)
    return 'Unauthorized', 403

# Templates
@app.route('/templates/<template_name>')
def serve_template(template_name):
    return render_template(template_name)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)