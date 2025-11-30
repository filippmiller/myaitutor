FROM python:3.11-slim

# Install system dependencies and Node.js
RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy frontend and build
COPY frontend ./frontend
WORKDIR /app/frontend
RUN npm install && npm run build

# Copy the rest of the application
WORKDIR /app
COPY . .

# Ensure static directory exists
RUN mkdir -p static/audio

# Set environment variables
ENV PORT=8080

# Start command
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
