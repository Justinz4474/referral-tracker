import os
from flask import request, session, redirect, url_for, abort, render_template_string
from sqlalchemy.orm import aliased
from app import db, User
from admin import TEMPLATE

def register_multi_admin(app):
    raw=os.environ.get('ADMIN_EMAILS') or os.environ.get('ADMIN_EMAIL','')
    emails={x.strip().lower() for x in raw.split(',') if x.strip()}
    with app.app_context():
        admin_ids=set(db.session.scalars(db.select(User.id).where(User.email.in_(emails))).all()) if emails else set()

    def dashboard():
        uid=session.get('uid')
        if not uid: return redirect(url_for('login'))
        if uid not in admin_ids or db.session.get(User,uid) is None: abort(403)
        q=request.args.get('q','').strip()[:100]
        child=aliased(User); inviter=aliased(User)
        counts=db.select(child.referred_by.label('uid'),db.func.count(child.id).label('n')).group_by(child.referred_by).subquery()
        query=db.select(User,db.func.coalesce(counts.c.n,0),inviter.name).outerjoin(counts,counts.c.uid==User.id).outerjoin(inviter,inviter.id==User.referred_by)
        if q: query=query.where(User.name.ilike('%'+q+'%'))
        sort=request.args.get('sort','referrals')
        query=query.order_by(User.id.desc()) if sort=='newest' else query.order_by(db.func.coalesce(counts.c.n,0).desc(),User.id.desc())
        try: page=max(1,int(request.args.get('page','1')))
        except ValueError: page=1
        rows=db.session.execute(query.limit(51).offset((page-1)*50)).all()
        total=db.session.scalar(db.select(db.func.count(User.id)))
        total_referred=db.session.scalar(db.select(db.func.count(User.id)).where(User.referred_by.is_not(None)))
        referrers=db.session.scalar(db.select(db.func.count(db.func.distinct(User.referred_by))).where(User.referred_by.is_not(None)))
        return render_template_string(TEMPLATE,rows=rows[:50],more=len(rows)>50,total=total,total_referred=total_referred,referrers=referrers,q=q,sort=sort,page=page)

    app.view_functions['admin_dashboard']=dashboard

    @app.after_request
    def navigation(response):
        if request.endpoint=='dashboard' and response.status_code==200 and response.mimetype=='text/html' and session.get('uid') in admin_ids:
            nav='<nav aria-label="Account navigation" style="display:flex;gap:12px;flex-wrap:wrap;margin:20px 0"><span style="background:#eae6ff;color:#6341c4;padding:12px 18px;border-radius:9px">My referrals</span><a href="/admin" style="background:#7355de;color:white;text-decoration:none;padding:12px 18px;border-radius:9px;font-weight:600">Admin dashboard &rarr;</a></nav>'
            response.set_data(response.get_data(as_text=True).replace('<section>',nav+'<section>',1))
        return response
