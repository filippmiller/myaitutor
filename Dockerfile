FROM python:3.11-slim

# Install system dependencies and Node.js
RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy application code
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Build frontend
WORKDIR /app/frontend
RUN npm install && npm run build

# Return to app root
WORKDIR /app

# Ensure static directory exists
RUN mkdir -p static/audio

# Set environment variables
ENV PORT=8080

# Start command
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
