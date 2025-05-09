from flask import Flask, render_template, request, redirect, url_for, flash, g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user
from urllib.parse import urlparse
import os

# Configuração inicial do Flask
app = Flask(__name__)

# Configurações básicas
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuração do banco de dados
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    raise RuntimeError("DATABASE_URL environment variable not set")

# Parse e ajuste da URL do PostgreSQL
parsed_url = urlparse(database_url)
if parsed_url.scheme == 'postgres':
    parsed_url = parsed_url._replace(scheme='postgresql+psycopg2')

app.config['SQLALCHEMY_DATABASE_URI'] = parsed_url.geturl()

# Inicialização das extensões
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Definição dos modelos
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(100))
    links = db.relationship('Link', backref='owner', lazy=True)

class Link(db.Model):
    __tablename__ = 'links'
    id = db.Column(db.Integer, primary_key=True)
    original_url = db.Column(db.String(500))
    custom_slug = db.Column(db.String(100), unique=True)
    clicks = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Criação de tabelas
def create_tables():
    with app.app_context():
        try:
            db.create_all()
            print("✅ Tabelas criadas com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao criar tabelas: {str(e)}")

# Verificação de tabelas no primeiro request
@app.before_request
def initialize_database():
    if not app.config.get('TABLES_CREATED'):
        create_tables()
        app.config['TABLES_CREATED'] = True

# Rotas
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')

    if not username or not password:
        flash('Preencha todos os campos')
        return redirect(url_for('index'))

    if User.query.filter_by(username=username).first():
        flash('Nome de usuário já existe')
        return redirect(url_for('index'))

    new_user = User(username=username, password=password)
    db.session.add(new_user)
    db.session.commit()
    login_user(new_user)
    
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    user = User.query.filter_by(username=username).first()

    if user and user.password == password:
        login_user(user)
        return redirect(url_for('dashboard'))
    
    flash('Credenciais inválidas')
    return redirect(url_for('index'))

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        original_url = request.form.get('url')
        custom_slug = request.form.get('slug')

        if not original_url or not custom_slug:
            flash('Preencha todos os campos')
            return redirect(url_for('dashboard'))

        if Link.query.filter_by(custom_slug=custom_slug).first():
            flash('Slug já está em uso')
            return redirect(url_for('dashboard'))

        new_link = Link(
            original_url=original_url,
            custom_slug=custom_slug,
            user_id=current_user.id
        )
        db.session.add(new_link)
        db.session.commit()
        flash('Link criado com sucesso!')

    user_links = Link.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', links=user_links)

@app.route('/<slug>')
def redirect_link(slug):
    link = Link.query.filter_by(custom_slug=slug).first()
    if link:
        link.clicks += 1
        db.session.commit()
        return redirect(link.original_url)
    return 'Link não encontrado', 404

@app.route('/stats/<slug>')
@login_required
def stats(slug):
    link = Link.query.filter_by(custom_slug=slug).first()
    if not link or link.user_id != current_user.id:
        return 'Não autorizado', 403
    return render_template('stats.html', link=link)

if __name__ == '__main__':
    create_tables()
    app.run(debug=False)