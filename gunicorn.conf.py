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
