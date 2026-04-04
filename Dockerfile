# Dockerfile

FROM python:3.12-slim

# Prevent .pyc files and buffer logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libreoffice \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first (layer caching)
COPY requirements.txt /app/

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy project
COPY . /app/

# Collect static files at build time
RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

CMD ["gunicorn", "joedocs.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]