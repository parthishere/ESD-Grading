# Procfile

web: python manage.py makemigrations && python manage.py migrate && python setup_roles.py && gunicorn ESD.wsgi:application -b 0.0.0.0:$PORT