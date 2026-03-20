#!/bin/bash
set -e

echo "========================================="
echo "🚀 Starting EveBook Application"
echo "========================================="
echo "Current directory: $(pwd)"
ls -la

# Wait for PostgreSQL
echo "📦 Waiting for PostgreSQL..."
while ! nc -z postgres 5432; do
  sleep 1
done
echo "✅ PostgreSQL is ready"

echo "🔧 Enabling pgvector extension..."
PGPASSWORD=postgres psql -h postgres -U postgres -d EventBooking -c "CREATE EXTENSION IF NOT EXISTS vector;"
echo "✅ pgvector extension enabled"

# Wait for Redis
echo "📦 Waiting for Redis..."
while ! nc -z redis 6379; do
  sleep 1
done
echo "✅ Redis is ready"

# Initialize database tables
echo "🗄️ Initializing database..."
cd /app
python -c "
from database import engine
from model import Base
print('Creating database tables...')
Base.metadata.create_all(bind=engine)
print('✅ Database tables created')
"

# Start MCP file handling server in background with retry
echo "🔌 Starting MCP file handling server..."
cd /app/AI/local_mcp/file_handle

# Check if file_handling_server.py exists
if [ -f "file_handling_server.py" ]; then
    # Install any missing MCP dependencies if needed
    pip install fastmcp mcp 2>/dev/null || true
    
    # Start the server
    python file_handling_server.py &
    MCP_PID=$!
    echo "✅ MCP server started (PID: $MCP_PID)"
    
    # Wait for MCP server to be ready
    sleep 3
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo "✅ MCP server is ready"
    else
        echo "⚠️ MCP server may not be ready yet (continuing anyway)"
    fi
else
    echo "⚠️ MCP server file not found, skipping"
    MCP_PID=""
fi
# Give MCP server a moment to start
sleep 2

# Start FastAPI backend
echo "🖥️ Starting FastAPI backend..."
cd /app
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait for backend to be ready
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
echo "✅ All services started!"
echo "📊 FastAPI:    http://localhost:8000"
echo "📈 Streamlit:  http://localhost:8501"
echo "🔌 MCP Server: http://localhost:8001"
echo "========================================="

wait $BACKEND_PID $FRONTEND_PID