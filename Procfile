web: gunicorn Andrea_jimenez.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --threads 1 --worker-class sync --worker-tmp-dir /dev/shm --log-file -
release: python manage.py migrate
