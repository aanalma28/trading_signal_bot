FROM python:3.12-slim-bullseye

WORKDIR /app

# Install procps agar perintah pgrep dan pkill bisa berjalan
RUN apt-get update && apt-get install -y procps && rm -rf /var/lib/apt/lists/*

# Copy requirements dan install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code backend
COPY backend/ ./backend/

# Jalankan server FastAPI
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
