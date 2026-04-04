release: python manage.py migrate && python manage.py collectstatic --noinput
web: gunicorn joedocs.wsgi:application --bind 0.0.0.0:$PORT