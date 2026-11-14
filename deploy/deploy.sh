#!/usr/bin/env bash
# Run on the server after pulling new code:  bash deploy/deploy.sh
set -euo pipefail
cd /srv/shiksha/app
/srv/shiksha/venv/bin/pip install -q -r requirements.txt
/srv/shiksha/venv/bin/python manage.py migrate --noinput
/srv/shiksha/venv/bin/python manage.py compilemessages -i venv
/srv/shiksha/venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart shiksha
echo "Deployed."
