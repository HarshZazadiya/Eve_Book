#!/bin/bash
set -e

echo "========================================="
echo "🚀 Starting EveBook Application"
echo "========================================="
echo "Current directory: $(pwd)"
echo "Listing files:"
ls -la

# Wait for PostgreSQL
echo "📦 Waiting for PostgreSQL..."
while ! nc -z postgres 5432; do
  sleep 1
done
echo "✅ PostgreSQL is ready"

# Wait for Redis
echo "📦 Waiting for Redis..."
while ! nc -z redis 6379; do
  sleep 1
done
echo "✅ Redis is ready"

# Wait for Ollama
echo "🤖 Waiting for Ollama..."
until curl -s http://ollama:11434/api/tags > /dev/null; do
  sleep 2
done
echo "✅ Ollama is ready"

# Pull nomic-embed-text model for embeddings
echo "📥 Checking for nomic-embed-text model..."
if ! curl -s http://ollama:11434/api/tags | grep -q "nomic-embed-text"; then
  echo "Downloading nomic-embed-text model..."
  curl -X POST http://ollama:11434/api/pull -d '{"name": "nomic-embed-text"}'
else
  echo "✅ nomic-embed-text model already exists"
fi

# Pull Llama model if not present
echo "📥 Checking for Llama 3.1 model..."
if ! curl -s http://ollama:11434/api/tags | grep -q "llama3.1:8b"; then
  echo "Downloading Llama 3.1 8B model (this may take a few minutes)..."
  curl -X POST http://ollama:11434/api/pull -d '{"name": "llama3.1:8b"}'
else
  echo "✅ Llama 3.1 model already exists"
fi

# Initialize database
echo "🗄️ Initializing database..."
cd /app
python -c "
from database import engine
from model import Base
print('Creating database tables...')
Base.metadata.create_all(bind=engine)
print('✅ Database tables created')
"

# Start FastAPI backend
echo "🖥️ Starting FastAPI backend..."
cd /app
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait for backend
echo "⏳ Waiting for backend to be ready..."
sleep 5
until curl -s http://localhost:8000/health > /dev/null; do
  sleep 2
done
echo "✅ Backend is ready"

# Start Streamlit frontend
echo "🎨 Starting Streamlit frontend..."
cd /app
streamlit run app.py --server.port 8501 --server.address 0.0.0.0 &
FRONTEND_PID=$!

echo "========================================="
echo "✅ All services started successfully!"
echo "📊 FastAPI: http://localhost:8000"
echo "📈 Streamlit: http://localhost:8501"
echo "========================================="

wait $BACKEND_PID $FRONTEND_PID