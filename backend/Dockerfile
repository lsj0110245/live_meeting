FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/media/recordings/audio \
    /app/media/recordings/video \
    /app/media/transcripts \
    /app/exports/csv \
    /app/exports/xlsx

# STT 모델 다운로드 (Build 과정에서 캐싱 - Secrets 사용으로 보안 강화)
RUN --mount=type=secret,id=hugging_face_token \
    python download_model.py

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
