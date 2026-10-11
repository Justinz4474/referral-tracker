def post_worker_init(worker):
    from app import app
    from admin import register_admin
    register_admin(app)
