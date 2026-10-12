import os, hashlib, hmac
from collections import Counter
from flask import request, session, redirect, url_for, abort, render_template_string
from sqlalchemy.exc import IntegrityError
from app import db, User, limiter
FORM_ID='1chZ8uChgTDFICJ6ZBMlT_NcfI2J7eZkMG89JBCg862g'
FORM_URL='https://docs.google.com/forms/d/e/1FAIpQLSd8ZxLQpfWGzq0F43oVhbOeeqi3F6SuLn4GEiaOk1iamjTEYQ/viewform'
def email_hash(email): return hashlib.sha256(email.strip().lower().encode()).hexdigest()
class FormCompletion(db.Model):
    email_hash=db.Column(db.String(64),primary_key=True)
    response_id=db.Column(db.String(256),unique=True,nullable=False)
    received_at=db.Column(db.DateTime,server_default=db.func.now())

PAGE='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Referral Tracker</title><style>*{box-sizing:border-box}body{margin:0;background:#f4f5fc;color:#25263d;font:15px system-ui}main{max-width:1050px;margin:35px auto;padding:20px}section{background:white;padding:24px;border:1px solid #e4e7ef;border-radius:16px;margin:20px 0}a{color:#6341c4}.button,button{display:inline-block;background:#7355de;color:white;text-decoration:none;border:0;border-radius:9px;padding:12px 18px;font:inherit;cursor:pointer}p{color:#656b80;line-height:1.6}.stats{display:flex;gap:15px;flex-wrap:wrap}.stat{flex:1;background:white;border:1px solid #e4e7ef;padding:20px;border-radius:16px;min-width:130px}.stat strong{display:block;font-size:30px;color:#7355de}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;text-align:left}th,td{padding:13px;border-bottom:1px solid #eee;white-space:nowrap}input,select{font:inherit;border:1px solid #d5d9e5;padding:11px;border-radius:8px}input.link{width:100%}nav,form.filters{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}.pending{color:#a66b00}.complete{color:#16854a}</style></head><body><main><h1>{{ 'Admin dashboard' if admin else 'Welcome, '+user.name }}</h1><nav><a href="/dashboard">My referrals</a>{% if is_admin %}<a class="button" href="/admin">Admin dashboard</a>{% endif %}</nav><p>A referral is credited only after a matching verified-email submission of Amanda’s form. Signup alone does not count.</p><div class="stats"><div class="stat">{{ 'Accounts' if admin else 'Referred accounts' }}<strong>{{ total }}</strong></div><div class="stat">Credited referrals<strong>{{ credited }}</strong></div><div class="stat">Pending referrals<strong>{{ pending }}</strong></div></div>{% if not admin %}<section><h2>Your referral link</h2><input class="link" readonly value="{{ link }}" onclick="this.select()" aria-label="Your referral link"><h2>Your form status: {{ 'Verified' if own_complete else 'Not yet verified' }}</h2><p>Submit the form while signed into Google with the same email you used for this website. Earlier submissions can also qualify after synchronization. If your order form is already submitted, do not submit a duplicate order just to earn referral credit.</p><a class="button" href="{{ form_url }}" target="_blank" rel="noopener noreferrer">Complete required form</a></section>{% endif %}<section><h2>{{ 'All accounts' if admin else 'Your referrals' }}</h2><form class="filters" method="get"><input name="q" value="{{ q }}" placeholder="Search names" aria-label="Search names"><select name="sort" aria-label="Sort"><option value="credited">Most credited referrals</option><option value="newest" {% if sort=='newest' %}selected{% endif %}>Newest accounts</option></select><button>Apply</button></form><div class="scroll"><table><tr><th>Name</th>{% if admin %}<th>Credited</th><th>Pending</th><th>Referred by</th>{% endif %}<th>Form status</th><th>Joined (UTC)</th></tr>{% for r in rows %}<tr><td>{{ r.name }}</td>{% if admin %}<td>{{ r.credit }}</td><td>{{ r.pending }}</td><td>{{ r.inviter }}</td>{% endif %}<td class="{{ 'complete' if r.complete else 'pending' }}">{{ 'Verified' if r.complete else 'Pending' }}</td><td>{{ r.date }}</td></tr>{% else %}<tr><td>No matching accounts.</td></tr>{% endfor %}</table></div><nav>{% if page>1 %}<a href="?page={{ page-1 }}&q={{ q|urlencode }}&sort={{ sort|urlencode }}">Previous</a>{% endif %}<span>Page {{ page }}</span>{% if more %}<a href="?page={{ page+1 }}&q={{ q|urlencode }}&sort={{ sort|urlencode }}">Next</a>{% endif %}</nav></section><form method="post" action="/logout"><input type="hidden" name="csrf_token" value="{{ csrf }}"><button>Log out</button></form><p>Submitting the form is not proof of payment or order confirmation. Duplicate submissions do not earn additional credit.</p></main></body></html>'''

def register_form_gate(app):
    from flask_wtf.csrf import generate_csrf
    with app.app_context():
        db.create_all()
        emails={e.strip().lower() for e in (os.environ.get('ADMIN_EMAILS') or os.environ.get('ADMIN_EMAIL','')).split(',') if e.strip()}
        admin_ids=set(db.session.scalars(db.select(User.id).where(User.email.in_(emails))).all()) if emails else set()

    @app.post('/webhooks/google-form')
    @app.extensions['csrf'].exempt
    @limiter.exempt
    def form_webhook():
        secret=os.environ.get('FORM_WEBHOOK_SECRET','')
        if len(secret)<32: abort(503)
        signature=hmac.new(secret.encode(),request.get_data(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature,request.headers.get('X-Form-Signature','')): abort(403)
        payload=request.get_json(silent=True) or {}
        email=payload.get('email',''); rid=payload.get('responseId','')
        if payload.get('formId')!=FORM_ID or not isinstance(email,str) or not isinstance(rid,str) or not 3<=len(email)<=254 or '@' not in email or not 1<=len(rid)<=256: abort(400)
        digest=email_hash(email)
        if db.session.get(FormCompletion,digest): return {'ok':True,'duplicate':True}
        db.session.add(FormCompletion(email_hash=digest,response_id=rid))
        try: db.session.commit()
        except IntegrityError:
            db.session.rollback()
            if db.session.get(FormCompletion,digest): return {'ok':True,'duplicate':True}
            abort(409)
        return {'ok':True}

    def show(admin=False):
        uid=session.get('uid'); user=db.session.get(User,uid) if uid else None
        if not user: return redirect(url_for('login'))
        if admin and uid not in admin_ids: abort(403)
        users=db.session.scalars(db.select(User).order_by(User.id.desc())).all()
        verified=set(db.session.scalars(db.select(FormCompletion.email_hash)).all())
        done={u.id:email_hash(u.email) in verified for u in users}
        credits=Counter(u.referred_by for u in users if u.referred_by and done[u.id])
        pendings=Counter(u.referred_by for u in users if u.referred_by and not done[u.id])
        names={u.id:u.name for u in users}
        selected=users if admin else [u for u in users if u.referred_by==uid]
        total=len(users) if admin else len(selected)
        credited=sum(credits.values()) if admin else credits[uid]
        pending=sum(pendings.values()) if admin else pendings[uid]
        q=request.args.get('q','').strip()[:100]; sort=request.args.get('sort','credited')
        selected=[u for u in selected if q.lower() in u.name.lower()]
        if admin and sort!='newest': selected.sort(key=lambda u:(credits[u.id],u.id),reverse=True)
        try: page=max(1,int(request.args.get('page','1')))
        except ValueError: page=1
        offset=(page-1)*50
        rows=[{'name':u.name,'credit':credits[u.id],'pending':pendings[u.id],'inviter':names.get(u.referred_by,'Direct signup'),'complete':done[u.id],'date':u.created_at.strftime('%Y-%m-%d %H:%M')} for u in selected[offset:offset+50]]
        base=os.environ.get('PUBLIC_BASE_URL') or ('https://'+os.environ['RENDER_EXTERNAL_HOSTNAME'])
        return render_template_string(PAGE,admin=admin,is_admin=uid in admin_ids,user=user,total=total,credited=credited,pending=pending,own_complete=done[uid],link=base.rstrip('/')+url_for('signup',ref=user.code),form_url=FORM_URL,rows=rows,page=page,more=len(selected)>offset+50,q=q,sort=sort,csrf=generate_csrf())
    app.view_functions['dashboard']=lambda:show(False)
    app.view_functions['admin_dashboard']=lambda:show(True)
