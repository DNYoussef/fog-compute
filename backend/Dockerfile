# Fog Compute Backend API - Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY backend/requirements.txt ./backend/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY src/ ./src/

# Expose API port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "uvicorn", "backend.server.main:app", "--host", "0.0.0.0", "--port", "8000"]
