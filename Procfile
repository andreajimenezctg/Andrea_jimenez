web: gunicorn Andrea_jimenez.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --threads 2 --worker-class gthread --worker-tmp-dir /dev/shm
release: python manage.py migrate
