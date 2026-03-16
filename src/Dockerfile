# FROM python:3.11-slim

# RUN apt-get update && apt-get install -y \
#     curl \
#     netcat-openbsd \
#     dos2unix \
#     && rm -rf /var/lib/apt/lists/*

# WORKDIR /app

# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# COPY . .

# RUN dos2unix /app/start.sh /app/wait_ollama.sh && \
#     chmod +x /app/start.sh /app/wait_ollama.sh

# RUN mkdir -p /app/uploads /app/vector_store

# EXPOSE 8000 8501

# CMD ["/app/start.sh"]

FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    curl \
    netcat-openbsd \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN dos2unix /app/start.sh && chmod +x /app/start.sh

RUN mkdir -p /app/uploads /app/vector_store

EXPOSE 8000 8501

CMD ["/app/start.sh"]