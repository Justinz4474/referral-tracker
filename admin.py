import os
from flask import request, session, redirect, url_for, abort, render_template_string
from sqlalchemy.orm import aliased
from app import db, User

def register_admin(app):
    email=os.environ.get('ADMIN_EMAIL','').strip().lower()
    with app.app_context():
        owner=db.session.scalar(db.select(User).where(User.email==email)) if email else None
        owner_id=owner.id if owner else None

    @app.get('/admin')
    def admin_dashboard():
        uid=session.get('uid')
        if not uid: return redirect(url_for('login'))
        user=db.session.get(User,uid)
        if owner_id is None or not user or user.id!=owner_id: abort(403)
        q=request.args.get('q','').strip()[:100]
        referred=aliased(User)
        counts=db.select(referred.referred_by.label('uid'),db.func.count(referred.id).label('n')).group_by(referred.referred_by).subquery()
        inviter=aliased(User)
        query=db.select(User,db.func.coalesce(counts.c.n,0),inviter.name).outerjoin(counts,counts.c.uid==User.id).outerjoin(inviter,inviter.id==User.referred_by)
        if q: query=query.where(User.name.ilike('%'+q+'%'))
        if request.args.get('sort')=='newest': query=query.order_by(User.id.desc())
        else: query=query.order_by(db.func.coalesce(counts.c.n,0).desc(),User.id.desc())
        try: page=max(1,int(request.args.get('page','1')))
        except ValueError: page=1
        rows=db.session.execute(query.limit(51).offset((page-1)*50)).all()
        more=len(rows)>50
        total=db.session.scalar(db.select(db.func.count(User.id)))
        total_referred=db.session.scalar(db.select(db.func.count(User.id)).where(User.referred_by.is_not(None)))
        referrers=db.session.scalar(db.select(db.func.count(db.func.distinct(User.referred_by))).where(User.referred_by.is_not(None)))
        return render_template_string(TEMPLATE,rows=rows[:50],total=total,total_referred=total_referred,referrers=referrers,q=q,sort=request.args.get('sort','referrals'),page=page,more=more)

TEMPLATE='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin - Referral Tracker</title><style>*{box-sizing:border-box}body{font:15px system-ui;background:#f4f5fc;color:#25263d;margin:0}main{max-width:1100px;margin:35px auto;padding:20px}a{color:#6341c4}section,.card{background:white;border:1px solid #e4e7ef;border-radius:16px;padding:22px}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:25px 0}.card strong{display:block;font-size:32px;color:#7355de}.card span{color:#656b80}form{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}input,select,button{font:inherit;padding:11px;border:1px solid #d5d9e5;border-radius:8px}input{flex:1;min-width:150px}button{background:#7355de;color:white;cursor:pointer}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;text-align:left}th,td{padding:14px 10px;border-bottom:1px solid #eee;white-space:nowrap}p{color:#656b80;line-height:1.6}.nav{display:flex;gap:20px;margin-top:20px}@media(max-width:550px){.stats{grid-template-columns:1fr}.card{padding:14px}}</style></head><body><main><h1>Admin dashboard</h1><p>View everyone’s referral activity. Access restricted to the designated administrator.</p><a href="{{ url_for('dashboard') }}">Back to my dashboard</a><div class="stats"><div class="card"><span>Total accounts</span><strong>{{ total }}</strong></div><div class="card"><span>Referred signups</span><strong>{{ total_referred }}</strong></div><div class="card"><span>People with referrals</span><strong>{{ referrers }}</strong></div></div><section><h2>All accounts</h2><form method="get"><input name="q" value="{{ q }}" placeholder="Search by name" aria-label="Search by name"><select name="sort" aria-label="Sort accounts"><option value="referrals" {% if sort!='newest' %}selected{% endif %}>Most referrals</option><option value="newest" {% if sort=='newest' %}selected{% endif %}>Newest accounts</option></select><button>Apply</button></form><div class="scroll"><table><thead><tr><th>Name</th><th>Referrals</th><th>Referred by</th><th>Joined (UTC)</th></tr></thead><tbody>{% for person,count,inviter in rows %}<tr><td>{{ person.name }}</td><td>{{ count }}</td><td>{{ inviter or 'Direct signup' }}</td><td>{{ person.created_at.strftime('%Y-%m-%d %H:%M') }}</td></tr>{% else %}<tr><td colspan="4">No matching accounts.</td></tr>{% endfor %}</tbody></table></div><div class="nav">{% if page>1 %}<a href="{{ url_for('admin_dashboard',q=q,sort=sort,page=page-1) }}">Previous</a>{% endif %}<span>Page {{ page }}</span>{% if more %}<a href="{{ url_for('admin_dashboard',q=q,sort=sort,page=page+1) }}">Next</a>{% endif %}</div></section><p>Counts represent accounts, not verified unique people. Emails and passwords are not displayed. Refresh to load the latest signups.</p></main></body></html>'''
