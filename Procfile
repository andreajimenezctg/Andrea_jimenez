web: gunicorn Andrea_jimenez.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 1 --timeout 120 --log-file -
release: python manage.py migrate
