def post_worker_init(worker):
    from app import app
    from admin import register_admin
    from recovery import register_recovery
    from multi_admin import register_multi_admin
    from form_gate import register_form_gate
    register_admin(app)
    register_recovery(app)
    register_multi_admin(app)
    register_form_gate(app)
    register_account_deletion(app)

def register_account_deletion(app):
    import os
    from flask import request, session, abort, redirect, url_for, render_template_string
    from flask_wtf.csrf import generate_csrf
    from app import db, User, limiter
    from form_gate import FormCompletion, email_hash

    def admin_emails():
        return {e.strip().lower() for e in (os.environ.get('ADMIN_EMAILS') or os.environ.get('ADMIN_EMAIL', '')).split(',') if e.strip()}

    def require_admin():
        user = db.session.get(User, session.get('uid')) if session.get('uid') else None
        if not user or user.email.lower() not in admin_emails():
            abort(403)
        return user

    template = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Manage accounts</title><style>body{font:15px system-ui;background:#f4f5fc;color:#25263d}main{max-width:1000px;margin:35px auto;padding:24px;background:white;border-radius:16px}table{width:100%;border-collapse:collapse}th,td{padding:12px;text-align:left;border-bottom:1px solid #ddd}input,button{font:inherit;padding:10px;margin:8px 0}button{background:#b62626;color:white;border:0;border-radius:8px}a{color:#6341c4}.scroll{overflow:auto}p{line-height:1.6}</style></head><body><main><h1>{{ 'Delete account' if target else 'Manage accounts' }}</h1><p><a href="/admin">Back to admin dashboard</a></p>{% if target %}<h2>{{ target.name }}</h2><p>Account email: {{ target.email }}</p><p>This permanently removes the website account, password, referral link, and saved form-verification record. Its signup will no longer count toward its referrer's credit. Other accounts remain, but their referral connection to this account is removed. The email can be used to sign up again.</p><p>This does not delete the actual Gmail account or the original Google Form response. A later form sync can restore verification for this email.</p>{% if error %}<p role="alert">{{ error }}</p>{% endif %}<form method="post"><input type="hidden" name="csrf_token" value="{{ csrf }}"><label>Type the account email to confirm deletion<br><input type="email" name="confirm_email" maxlength="254" required autocomplete="off"></label><br><button>Delete account permanently</button></form><p><a href="/admin/accounts">Cancel</a></p>{% else %}<p>Admin accounts are protected. Deletion requires confirmation and removes saved website form verification.</p><form method="get"><input name="q" value="{{ q }}" placeholder="Search name or email" aria-label="Search accounts"><button style="background:#7355de">Search</button></form><div class="scroll"><table><tr><th>Name</th><th>Email</th><th>Action</th></tr>{% for u in users %}<tr><td>{{ u.name }}</td><td>{{ u.email }}</td><td>{% if u.email.lower() in protected %}Admin — protected{% else %}<a href="{{ url_for('admin_delete_account', user_id=u.id) }}">Delete account</a>{% endif %}</td></tr>{% else %}<tr><td colspan="3">No matching accounts.</td></tr>{% endfor %}</table></div><p>{% if page>1 %}<a href="?page={{ page-1 }}&q={{ q|urlencode }}">Previous</a>{% endif %} Page {{ page }} {% if more %}<a href="?page={{ page+1 }}&q={{ q|urlencode }}">Next</a>{% endif %}</p>{% endif %}</main></body></html>'''

    @app.get('/admin/accounts')
    def admin_accounts():
        require_admin()
        q = request.args.get('q', '').strip()[:254]
        try:
            page = max(1, int(request.args.get('page', '1')))
        except ValueError:
            page = 1
        query = db.select(User)
        if q:
            query = query.where(db.or_(User.name.ilike('%' + q + '%'), User.email.ilike('%' + q + '%')))
        users = db.session.scalars(query.order_by(User.id.desc()).offset((page-1)*50).limit(51)).all()
        return render_template_string(template, target=None, users=users[:50], protected=admin_emails(), q=q, page=page, more=len(users)>50)

    @app.route('/admin/accounts/<int:user_id>/delete', methods=['GET', 'POST'])
    @limiter.limit('30 per hour')
    def admin_delete_account(user_id):
        actor = require_admin()
        target = db.session.scalar(db.select(User).where(User.id == user_id).with_for_update())
        if not target:
            abort(404)
        if target.id == actor.id or target.email.lower() in admin_emails():
            abort(403)
        if request.method == 'GET':
            return render_template_string(template, target=target, csrf=generate_csrf(), error=None)
        if request.form.get('confirm_email', '').strip().lower() != target.email.lower():
            return render_template_string(template, target=target, csrf=generate_csrf(), error='Email does not match. Nothing was deleted.'), 400
        try:
            db.session.execute(db.update(User).where(User.referred_by == target.id).values(referred_by=None))
            db.session.execute(db.delete(FormCompletion).where(FormCompletion.email_hash == email_hash(target.email)))
            db.session.delete(target)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        return redirect(url_for('admin_accounts'))

    @app.after_request
    def account_management_link(response):
        if request.endpoint == 'admin_dashboard' and response.status_code == 200 and response.mimetype == 'text/html':
            response.set_data(response.get_data(as_text=True).replace('</nav>', '<a class="button" href="/admin/accounts">Manage / delete accounts</a></nav>', 1))
        return response
