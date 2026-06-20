FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AUDIOMIND_DATA_DIR=/app/data
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr libsndfile1 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-tts.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-tts.txt
COPY . .
EXPOSE 8000 8501
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
