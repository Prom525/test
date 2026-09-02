FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt \
 && adduser --disabled-password --gecos '' appuser \
 && mkdir -p /data && chown -R appuser:appuser /app /data

RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libharfbuzz-subset0 \
    libffi-dev \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libglib2.0-0 \
    shared-mime-info \
    fonts-dejavu-core \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-nld \
    && rm -rf /var/lib/apt/lists/*

COPY app ./app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
