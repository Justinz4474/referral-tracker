# Referral Tracker
Automatic signup referral tracker using Flask and PostgreSQL.

Set DATABASE_URL and SECRET_KEY in the hosting environment, never in GitHub. Build: pip install -r requirements.txt. Start: flask --app app init-db && gunicorn --workers 1 --bind 0.0.0.0:$PORT app:app. HTTPS is required for session cookies. Render supplies RENDER_EXTERNAL_HOSTNAME for referral links; optionally set PUBLIC_BASE_URL.

A new account receives a unique link. The latest valid referral link visited in the same browser session is credited on signup. Invalid codes clear attribution. Existing accounts and clicks are not counted. Referrers see names and signup dates only.

Starter demo, not a production identity service: no email verification, password reset, automated account deletion, or advanced fraud prevention. Counts do not prove unique people. Rate limits are per-process and reset on restart. Before commercial launch add verified email, shared rate-limit storage, privacy/deletion processes, backups, monitoring, and a security review. Do not collect sensitive or regulated information.
