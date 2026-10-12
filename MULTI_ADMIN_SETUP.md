# Multiple administrators
ADMIN_EMAILS is a private comma-separated list configured in Render. It overrides the legacy ADMIN_EMAIL; if absent, the legacy setting is used. No account identifiers are stored in public code.

Only already-existing accounts matching the list are resolved to IDs at worker startup. A new account created later will not automatically receive access: redeploy after verifying the intended user created it. This app does not verify email ownership, so confirm identity before granting privileges. Both dashboard authorization and navigation use the same startup ID set. To remove an administrator, update ADMIN_EMAILS and redeploy. Existing accounts, referrals, recovery and database settings are preserved.
