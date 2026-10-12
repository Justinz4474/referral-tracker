def post_worker_init(worker):
    from app import app
    from admin import register_admin
    from recovery import register_recovery
    from admin_navigation import register_admin_navigation
    register_admin(app)
    register_recovery(app)
    register_admin_navigation(app)
