#!/bin/bash
set -e

echo "========================================="
echo " EveBook API starting up"
echo "========================================="

# ── Wait for PostgreSQL ──────────────────────
echo "⏳ Waiting for PostgreSQL..."
until pg_isready -h postgres -U postgres -d EventBooking; do
  sleep 2
done
echo "✅ PostgreSQL ready"

# ── Enable pgvector extension ────────────────
echo "🔧 Enabling pgvector..."
PGPASSWORD=postgres psql -h postgres -U postgres -d EventBooking \
  -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || true
echo "✅ pgvector ready"

# ── Create all ORM tables ────────────────────
echo "🗄️  Creating database tables..."
cd /app
python - <<'EOF'
from database import engine
from model import Base
Base.metadata.create_all(bind=engine)
print("✅ Tables ready")
EOF

until nc -z redis 6379; do
  sleep 1
done

# ── Start Uvicorn ────────────────────────────
echo "🚀 Starting FastAPI on :8000"
exec uvicorn main:app --host 0.0.0.0 --port 8000