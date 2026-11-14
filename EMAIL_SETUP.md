# Where to put your email settings

Create a file named **`.env`** in the project root — the same folder as `manage.py`. Django reads it automatically
(copy `.env.example` as a starting point). **Never share or commit `.env`.**

## Option A — your company Microsoft 365 mailbox (recommended)

Ask IT for a **service mailbox** such as `shiksha@vishakha.com` (or `noreply@vishakha.com`) and make sure
"Authenticated SMTP" is enabled for it. Then put this in `.env`:

```
EMAIL_HOST=smtp.office365.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=shiksha@vishakha.com
EMAIL_HOST_PASSWORD=the-mailbox-password-or-app-password
DEFAULT_FROM_EMAIL=Project Shiksha <shiksha@vishakha.com>
```

Notes
- Microsoft 365 often blocks plain SMTP login for personal mailboxes or when MFA is on. If sending fails with an
  "authentication" error, ask IT to (a) enable *Authenticated SMTP* for that mailbox, or (b) create an app password,
  or (c) give you an **SMTP relay** host — in that case set `EMAIL_HOST` to that relay and leave the user/password empty.
- Don't use your personal mailbox for this: its password would sit in a text file.

## Option B — nothing to set up (local testing)
Leave `EMAIL_HOST` empty. The reset / verification emails are **printed in the terminal** where `runserver` is running.
Copy the link from there.

## Check that it works
```
python manage.py send_test_email your.name@vishakha.com
```
It prints which server it uses and sends a sample branded email.

## Optional: logo inside emails
Email apps can only load images from a public web address. After the site is live, set
`EMAIL_LOGO_URL=https://YOUR-DOMAIN/static/img/brand/logo.png` — until then the email header shows the word VISHAKHA.

## What emails the app sends
| When | Email |
|---|---|
| Someone creates an account | "Verify your Project Shiksha account" (link works 3 hours) |
| Someone clicks *Forgot password* | "Reset your Project Shiksha password" (link works 3 hours, one use) |
