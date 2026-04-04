FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY . /app/

RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

<<<<<<< HEAD
CMD ["sh", "-c", "gunicorn joedocs.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120 --log-level debug --access-logfile - --error-logfile -"]
=======
CMD ["gunicorn", "joedocs.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
>>>>>>> c6e597ce91daee7fa1565ac43570ca68843b2e28
