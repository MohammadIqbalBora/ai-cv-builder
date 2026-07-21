# Procfile declares process types for Heroku-like platforms
# The `release` process runs once at deploy time to apply DB migrations
release: python manage.py migrate
# The `web` process starts the WSGI server (Gunicorn) for the web app
web: gunicorn config.wsgi
