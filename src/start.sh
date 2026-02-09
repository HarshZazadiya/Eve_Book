#!/bin/sh

echo "Waiting for Postgres..."

while ! nc -z postgres 5432; do
  sleep 1
done

echo "Postgres started"

echo "Starting FastAPI..."
uvicorn main:app --host 0.0.0.0 --port 8000 &

echo "Starting Streamlit..."
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
