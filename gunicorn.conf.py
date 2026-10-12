def post_worker_init(worker):
    from app import app
    from admin import register_admin
    from recovery import register_recovery
    register_admin(app)
    register_recovery(app)
