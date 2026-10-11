import os, secrets
from flask import Flask, request, session, redirect, url_for, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
uri = os.environ['DATABASE_URL']
if uri.startswith('postgres://'): uri = uri.replace('postgres://', 'postgresql+psycopg://', 1)
elif uri.startswith('postgresql://'): uri = uri.replace('postgresql://', 'postgresql+psycopg://', 1)
app.config.update(SECRET_KEY=os.environ['SECRET_KEY'], SQLALCHEMY_DATABASE_URI=uri, SQLALCHEMY_TRACK_MODIFICATIONS=False, SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', MAX_CONTENT_LENGTH=16384)
db = SQLAlchemy(app)
CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, default_limits=['300 per hour'], storage_uri='memory://')
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password = db.Column(db.Text, nullable=False)
    code = db.Column(db.String(40), unique=True, nullable=False)
    referred_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

PAGE = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Referral Tracker</title><style>*{box-sizing:border-box}body{margin:0;background:#f4f5fc;color:#24243c;font:16px system-ui}main{max-width:800px;margin:40px auto;padding:20px}section{background:white;border:1px solid #e4e7ef;border-radius:18px;padding:25px;margin:20px 0}p{color:#656b80;line-height:1.6}label{display:block;margin-top:16px}input{width:100%;padding:12px;border:1px solid #cfd4e2;border-radius:9px;font:inherit;margin-top:6px}button{background:#7355de;color:white;padding:12px 20px;border:0;border-radius:9px;font:inherit;margin-top:16px;cursor:pointer}a{color:#6341c4}.error{color:#b62626}.count{font-size:44px;color:#7355de}.row{display:flex;justify-content:space-between;gap:12px;padding:12px 0;border-bottom:1px solid #eee}.hint{font-size:13px}</style></head><body><main><h1>Referral Tracker</h1><p>Share your link. Track completed signups.</p>{% if error %}<p class="error" role="alert">{{ error }}</p>{% endif %}{% if mode == 'dashboard' %}<section><h2>Welcome, {{ user.name }}</h2><label>Your referral link<input readonly value="{{ link }}" onclick="this.select()"></label><p>Copy this link and share it. New accounts created through it are automatically credited to you.</p></section><section><h2>Completed signups</h2><div class="count">{{ referrals|length }}</div>{% for r in referrals %}<div class="row"><span>{{ r.name }}</span><span>{{ r.created_at.strftime('%Y-%m-%d') }}</span></div>{% else %}<p>No referrals yet.</p>{% endfor %}</section><form method="post" action="{{ url_for('logout') }}"><input type="hidden" name="csrf_token" value="{{ token }}"><button>Log out</button></form>{% else %}<section><h2>{{ 'Create your account' if mode == 'signup' else 'Log in' }}</h2>{% if referrer %}<p>Invited by {{ referrer.name }}</p>{% endif %}<form method="post"><input type="hidden" name="csrf_token" value="{{ token }}">{% if mode == 'signup' %}<label>Name<input name="name" required maxlength="100" autocomplete="name"></label>{% endif %}<label>Email<input type="email" name="email" required maxlength="254" autocomplete="email"></label><label>Password<input type="password" name="password" required minlength="12" maxlength="256" autocomplete="{{ 'new-password' if mode == 'signup' else 'current-password' }}"></label>{% if mode == 'signup' %}<p class="hint">Use at least 12 characters. Your referrer sees your name and signup date, not your email or password. This demo does not verify email ownership. Do not enter sensitive information.</p>{% endif %}<button>{{ 'Sign up' if mode == 'signup' else 'Log in' }}</button></form><p><a href="{{ url_for('login' if mode == 'signup' else 'signup') }}">{{ 'Already registered? Log in' if mode == 'signup' else 'Create an account' }}</a></p></section>{% endif %}<p class="hint">Starter demo: signup counts are not verified unique people. No payments or rewards are issued.</p></main></body></html>'''
def page(mode, **kw): return render_template_string(PAGE, mode=mode, token=generate_csrf(), **kw)
@app.after_request
def headers(r):
    r.headers['Cache-Control']='no-store'
    r.headers['X-Content-Type-Options']='nosniff'
    r.headers['X-Frame-Options']='DENY'
    r.headers['Referrer-Policy']='same-origin'
    return r
@app.get('/')
def index(): return redirect(url_for('dashboard' if session.get('uid') else 'signup'))
@app.route('/signup', methods=['GET','POST'])
@limiter.limit('15 per minute')
def signup():
    if session.get('uid'): return redirect(url_for('dashboard'))
    if request.method == 'GET' and 'ref' in request.args:
        inviter = db.session.scalar(db.select(User).where(User.code == request.args['ref']))
        if inviter: session['ref'] = inviter.code
        else: session.pop('ref', None)
    referrer = db.session.scalar(db.select(User).where(User.code == session.get('ref','')))
    error = None
    if request.method == 'POST':
        name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        if not (1 <= len(name) <= 100 and 3 <= len(email) <= 254 and '@' in email and 12 <= len(password) <= 256): error='Enter a name, email, and password of 12–256 characters.'
        else:
            user=User(name=name,email=email,password=generate_password_hash(password),code=secrets.token_urlsafe(18),referred_by=referrer.id if referrer else None)
            db.session.add(user)
            try:
                db.session.commit(); uid=user.id; session.clear(); session['uid']=uid
                return redirect(url_for('dashboard'))
            except IntegrityError:
                db.session.rollback(); error='Email already registered. Please log in.'
    return page('signup', error=error, referrer=referrer)
@app.route('/login',methods=['GET','POST'])
@limiter.limit('10 per minute')
def login():
    error=None
    if request.method=='POST':
        user=db.session.scalar(db.select(User).where(User.email==request.form.get('email','').strip().lower()))
        if user and check_password_hash(user.password,request.form.get('password','')):
            session.clear(); session['uid']=user.id; return redirect(url_for('dashboard'))
        error='Incorrect email or password.'
    return page('login',error=error)
@app.get('/dashboard')
def dashboard():
    user=db.session.get(User,session.get('uid')) if session.get('uid') else None
    if not user: return redirect(url_for('login'))
    referrals=db.session.scalars(db.select(User).where(User.referred_by==user.id).order_by(User.id.desc())).all()
    base=os.environ.get('PUBLIC_BASE_URL') or ('https://'+os.environ['RENDER_EXTERNAL_HOSTNAME'])
    return page('dashboard',user=user,referrals=referrals,link=base.rstrip('/')+url_for('signup',ref=user.code))
@app.post('/logout')
def logout():
    session.clear(); return redirect(url_for('login'))
@app.get('/health')
def health(): return {'status':'ok'}
@app.cli.command('init-db')
def init_db(): db.create_all()
