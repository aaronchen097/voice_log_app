FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --force-reinstall -r requirements.txt

# Copy application source code
COPY backend/ ./

# Copy frontend files (includes static files)
COPY frontend ./frontend

EXPOSE 31101

# Start FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "31101"]
