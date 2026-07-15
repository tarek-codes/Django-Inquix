FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    espeak-ng \
    antiword \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers for crawl4ai
RUN python -m playwright install chromium
RUN python -m playwright install-deps chromium

COPY . .

CMD ["sh", "-c", "python manage.py migrate && uvicorn app.asgi:application --host 0.0.0.0 --port 8000 --reload"]
