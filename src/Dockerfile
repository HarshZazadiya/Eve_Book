FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    netcat-openbsd \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/uploads /app/vector_store /app/src/AI/local_mcp/file_handle/workspace

COPY start.sh /app/start.sh
# Make scripts executable
RUN chmod +x /app/start.sh

# Expose ports
EXPOSE 8000 8501 8001

CMD ["/app/start.sh"]