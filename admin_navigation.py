import os
from flask import request, session
from app import db, User

def register_admin_navigation(app):
    email=os.environ.get('ADMIN_EMAIL','').strip().lower()
    with app.app_context():
        owner=db.session.scalar(db.select(User).where(User.email==email)) if email else None
        owner_id=owner.id if owner else None

    @app.after_request
    def add_admin_button(response):
        if request.endpoint=='dashboard' and response.status_code==200 and response.mimetype=='text/html' and owner_id is not None and session.get('uid')==owner_id:
            button='<nav aria-label="Account navigation" style="display:flex;gap:12px;flex-wrap:wrap;margin:20px 0"><span style="display:inline-block;background:#eae6ff;color:#6341c4;padding:12px 18px;border-radius:9px">My referrals</span><a href="/admin" style="display:inline-block;background:#7355de;color:white;text-decoration:none;padding:12px 18px;border-radius:9px;font-weight:600">Admin dashboard &rarr;</a></nav>'
            response.set_data(response.get_data(as_text=True).replace('<section>',button+'<section>',1))
        return response
