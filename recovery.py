import os, json, secrets, hashlib, hmac
from urllib.request import Request, urlopen
from flask import request, session, redirect, url_for, render_template_string
from flask_wtf.csrf import generate_csrf
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash
from app import db, User, limiter

def fingerprint(user): return hashlib.sha256(user.password.encode()).hexdigest()

TEMPLATE='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Password recovery</title><style>body{font:16px system-ui;background:#f4f5fc;color:#25263d;margin:0}main{max-width:450px;margin:50px auto;padding:25px}section{background:white;border:1px solid #e4e7ef;border-radius:18px;padding:25px}label{display:block;margin-top:18px}input{box-sizing:border-box;width:100%;font:inherit;padding:12px;border:1px solid #ccd2e0;border-radius:9px;margin-top:6px}button{font:inherit;background:#7355de;color:white;border:0;border-radius:9px;padding:12px 18px;margin-top:20px;cursor:pointer}p{color:#656b80;line-height:1.6}a{color:#6341c4}</style></head><body><main><section><h1>{{ 'Choose a new password' if reset else 'Forgot password?' }}</h1>{% if message %}<p role="status">{{ message }}</p>{% endif %}{% if show_form %}<form method="post"><input type="hidden" name="csrf_token" value="{{ csrf }}">{% if reset %}<label>New password<input name="password" type="password" minlength="12" maxlength="256" required autocomplete="new-password"></label><label>Confirm new password<input name="confirm" type="password" minlength="12" maxlength="256" required autocomplete="new-password"></label>{% else %}<p>Enter your account email to request a reset link.</p><label>Email<input name="email" type="email" maxlength="254" required autocomplete="email"></label>{% endif %}<button>{{ 'Save new password' if reset else 'Email reset link' }}</button></form>{% endif %}<p><a href="{{ url_for('login') }}">Back to login</a></p></section></main></body></html>'''

def register_recovery(app):
    signer=URLSafeTimedSerializer(app.secret_key,salt='password-reset-v1')
    def page(reset=False,message=None,show_form=True):
        return render_template_string(TEMPLATE,reset=reset,message=message,show_form=show_form,csrf=generate_csrf())

    @app.before_request
    def check_session():
        uid=session.get('uid')
        if uid:
            user=db.session.get(User,uid)
            if not user or not hmac.compare_digest(session.get('pw_version',''),fingerprint(user)):
                session.clear()

    @app.after_request
    def session_and_login_link(response):
        if request.endpoint in ('login','signup') and request.method=='POST' and response.status_code==302 and session.get('uid'):
            user=db.session.get(User,session['uid'])
            if user: session['pw_version']=fingerprint(user)
        if request.endpoint=='login' and response.status_code==200 and response.mimetype=='text/html':
            response.set_data(response.get_data(as_text=True).replace('</section>','<p><a href="/forgot-password">Forgot password?</a></p></section>',1))
        if request.endpoint in ('forgot_password','reset_password'):
            response.headers['Referrer-Policy']='no-referrer'
            response.headers['Cache-Control']='no-store'
        return response

    @app.route('/forgot-password',methods=['GET','POST'])
    @limiter.limit('5 per hour')
    def forgot_password():
        if request.method=='GET': return page()
        email=request.form.get('email','').strip().lower()[:254]
        user=db.session.scalar(db.select(User).where(User.email==email))
        key=os.environ.get('BREVO_API_KEY'); sender=os.environ.get('MAIL_FROM_EMAIL')
        if user and key and sender:
            token=signer.dumps({'uid':user.id,'v':fingerprint(user),'nonce':secrets.token_urlsafe(24)})
            base=os.environ.get('PUBLIC_BASE_URL') or ('https://'+os.environ['RENDER_EXTERNAL_HOSTNAME'])
            link=base.rstrip('/')+url_for('reset_password',token=token)
            payload={'sender':{'name':os.environ.get('MAIL_FROM_NAME','Referral Tracker'),'email':sender},'to':[{'email':user.email}],'subject':'Reset your Referral Tracker password','textContent':'A password reset was requested for your account. Open this link within 15 minutes:\n\n'+link+'\n\nIf you did not request this, ignore this email. Your password has not changed.'}
            try:
                req=Request('https://api.brevo.com/v3/smtp/email',data=json.dumps(payload).encode(),headers={'api-key':key,'Content-Type':'application/json','Accept':'application/json'},method='POST')
                with urlopen(req,timeout=10) as result: result.read()
            except Exception:
                app.logger.error('Password recovery email could not be sent; check private email settings and Brevo account status.')
        elif not key or not sender:
            app.logger.error('Password recovery email settings are missing.')
        return page(message='If that email is registered, a reset link will be sent. Check your inbox and spam folder. Links expire after 15 minutes.',show_form=False)

    @app.route('/reset-password/<token>',methods=['GET','POST'])
    @limiter.limit('20 per hour')
    def reset_password(token):
        try:
            data=signer.loads(token,max_age=900)
            user=db.session.scalar(db.select(User).where(User.id==data['uid']).with_for_update())
            valid=user is not None and hmac.compare_digest(data.get('v',''),fingerprint(user))
        except (BadSignature,SignatureExpired,KeyError,TypeError): valid=False
        if not valid:
            db.session.rollback()
            return page(reset=True,message='This reset link is invalid, expired, or already used. Request a new link.',show_form=False),400
        if request.method=='GET':
            db.session.rollback()
            return page(reset=True)
        password=request.form.get('password','')
        if not 12<=len(password)<=256 or password!=request.form.get('confirm',''):
            db.session.rollback()
            return page(reset=True,message='Use 12–256 characters and enter the same password in both fields.'),400
        user.password=generate_password_hash(password)
        db.session.commit()
        session.clear()
        return page(reset=True,message='Your password has been changed. Log in with your new password.',show_form=False)
