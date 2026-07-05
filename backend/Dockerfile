FROM python:3.12-slim
WORKDIR /code
# Tesseract (OCR locale, opzionale) + dipendenze PDF/immagini
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-ita poppler-utils \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
