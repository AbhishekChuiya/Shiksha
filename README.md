# Project Shiksha — In-house LMS (Django)

Multilingual learning platform for Vishakha Group plants (VGPL 1, VGPL 2, VMPL P1, VMPL P2, VRPL).

## Run locally

```bash
python3 -m venv shiksha_env && source shiksha_env/bin/activate   # Windows: shiksha_env\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo          # demo plants, VMPL P1 modules, 2 users
python manage.py runserver
```

Open http://127.0.0.1:8000. Test logins (password `Test@12345`): `test_user`, `test_user2`, `test_manager`, `test_admin` (or `<name>@vishakha.com`). Only company-domain accounts can sign in. Content management is the admin panel at `/manage/`. The technical Django admin (`/admin/`) is only for superusers created with `python manage.py createsuperuser` — the Admin role in the panel never grants it.

Run the tests with `python manage.py test tests`.

## Admin panel
Admins manage everything at `/manage/` (plants, modules, steps, photos, quizzes, SOPs, users, moderation, reports). See `ADMIN_GUIDE.md`.

## Project layout

| App | What it owns |
|---|---|
| `accounts` | Custom user (email/employee-ID login), Learner/Admin role, plant access, Manager/HOD approval scopes |
| `plants` | Plant → Department → Process, plant photos |
| `learning` | Modules, safety guidelines, SOP steps (EN/HI), videos, problem–solution, discussion, progress |
| `sops` | SOP library with controlled versions (only one approved/active), access log |
| `quizzes` | Quiz per module, questions/choices, attempts, pass mark, lock until all steps done |
| `certificates` | Auto-issued on completion (all steps + quiz passed), printable |
| `incidents` | Incident reporting with attachments, status workflow, audit trail |
| `knowledge` | Knowledge Base: categorised PDFs, documents, videos and links (plus SOPs and module videos, shown automatically) |
| `panel` | The admin panel (`/manage/`): row editors, forms, imports, reports |
| `core` | Dashboard, plant overview, plant switcher, search, audit log, management commands |

### Learning flow

1. A learner opens a module and goes to the SOPs tab.
2. They must agree to the safety guidelines before the steps unlock.
3. They mark each step complete, with optional read-aloud.
4. The quiz unlocks once every step is complete; the pass mark is 80% by default.
5. Passing the quiz completes the module and issues a certificate.

## Loading real content

**SOP steps from CSV** (columns: `step,text,text_hi`):
```bash
python manage.py import_steps vmpl_melt_cast melt_cast_steps.csv
```

**Quiz questions from CSV** (columns: `question,option_a,option_b,option_c,option_d,correct,kind,explanation,question_hi`; `correct` is A–D):
```bash
python manage.py import_quiz vmpl_melt_cast melt_cast_quiz.csv --pass 80
```

Everything else (plants, modules, safety guidelines, SOP documents/versions, videos, users) is managed in the admin panel (`/manage/`).

> Demo steps are marked `[DEMO]`. Replace them with the approved SOP text before go-live.

## Languages

UI: English and Hindi (`hi`). Content fields have `_hi` variants that show up when the UI is set to Hindi.

Read-aloud uses the browser's speech engine and picks the voice from the **content** language (it detects Devanagari script), not from the menu language.

Translation files live in `locale/`. On the server, use Django's `makemessages` and `compilemessages` (needs `gettext`).

## Deploying to a Linux server (Ubuntu)

```bash
sudo apt install python3-venv postgresql nginx gettext
sudo -u postgres createuser shiksha -P
sudo -u postgres createdb shiksha -O shiksha
sudo useradd -r -m -d /srv/shiksha shiksha
# copy code to /srv/shiksha/app, create /srv/shiksha/venv, then:
cp .env.example .env    # fill in secret key, domain, DATABASE_URL
python manage.py migrate && python manage.py createsuperuser
python manage.py collectstatic --noinput
sudo cp deploy/shiksha.service /etc/systemd/system/ && sudo systemctl enable --now shiksha
sudo cp deploy/nginx-shiksha.conf /etc/nginx/sites-available/shiksha   # edit domain + cert paths
sudo ln -s /etc/nginx/sites-available/shiksha /etc/nginx/sites-enabled/ && sudo nginx -t && sudo systemctl reload nginx
```

For later releases, pull the new code and run `bash deploy/deploy.sh`.

## Roadmap status

**Phase 1 (go-live 1 Dec 2026)**
- Done: login, plant access, plant switcher, dashboard, plant overview, modules, safety gate, SOP steps, quizzes, certificates, SOP library with versioning, incidents, search, admin, audit log.
- Pending: Microsoft Entra ID SSO (needs the app registration from IT) and admin reports.

**Phase 2**
- Done (foundation): video lessons, read-aloud, Hindi UI.
- To do: RAG AI assistant, expanded reports.

**Phase 3:** feedback/suggestions, HOD approvals, Learning Book, SOP-change DOA flow, gamification, PWA.
