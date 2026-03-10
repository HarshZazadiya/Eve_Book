# 🎟 Eve_Book — Event Booking Platform

A full-stack **Event Booking Application** with integrated **AI Assistant**, built using **FastAPI**, **PostgreSQL**, **Redis**, **LangGraph**, and **Streamlit**. 

The platform features role-based authentication and an intelligent conversational agent that can answer questions and perform actions.

---

## 🚀 Core Features

### 👤 User
- Browse available events with document previews
- Book tickets with wallet payment
- Cancel bookings for instant refund
- Wallet system with easy top-up
- Promote to Host (paid upgrade)
- **AI Assistant** – Ask about events, check balance, manage bookings

### 🏢 Host
- Create events with optional PDF upload
- Manage and update hosted events
- Delete events with automatic refunds
- Earn money directly into wallet from bookings
- **AI Assistant** – Get help managing your events

### 🛠️ Admin
- View all users, hosts, and events
- Monitor all bookings and wallets
- Delete any event or booking with proper refunds
- Demote hosts back to users
- **AI Assistant** – Request system statistics and reports

---

## ⚡ Tech Stack

| Layer | Technology |
|--------|-------------|
| Backend | FastAPI |
| Database | PostgreSQL |
| Cache | Redis |
| Frontend | Streamlit |
| Authentication | JWT Role-Based Auth |
| Containerization | Docker + Docker Compose |

---

## 🧠 AI Architecture Highlights

| Component | Technology |
|-----------|-------------|
| LLM Engine | Ollama with Llama 3.1 8B |
| AI Agent Framework | LangGraph |
| RAG Pipeline | FAISS Vector Store + LangChain |
| Embeddings | nomic-embed-text |
| Conversation Memory | Thread-based chat history |
---

## 🧠 Architecture Highlights

✔ Role Based Authorization  
✔ Redis caching for fast responses  
✔ Wallet transaction system  
✔ Atomic booking & refund logic  
✔ Dockerized micro-service style setup  

---

## 🧠 Key AI Features

✔ **Role-Aware Agent**      – The AI knows if you're a user, host, or admin and only performs actions you're allowed to do  
✔ **Document Q&A**          – Upload event PDFs and ask the AI detailed questions  
✔ **Tool-Using Assistant**  – Can book events, check wallets, and more through natural conversation  
✔ **Privacy-First**         – All AI processing happens locally – no data leaves your machine  
✔ **Conversation History**  – Remembers context across multiple messages

---
## 📦 Docker Hub Image

👉 **Multi-Version Repository**: [harshzazadiya/eve_book](https://hub.docker.com/r/harshzazadiya/eve_book)

| Tag | Version | Description |
|-----|---------|-------------|
| `latest` | v1.0 | Stable version without AI |
| `v2.0` | v2.0 | **NEW** AI-powered version |

---

# 🐳 Running the Application (Recommended Way)

The easiest way to run the complete AI-powered application is using **Docker Compose**.

## ✅ Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)
- At least **8GB RAM** (16GB recommended for AI models)

---

## ✅ Step 1 — Install Requirements

Make sure you have installed:

- Docker  
- Docker Compose  

---

## ✅ Step 2 — Create `docker-compose.yaml`

Create a file named : docker-compose.yaml
Paste this inside:

```yaml
vversion: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    container_name: event_postgres
    restart: always
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: EventBooking
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: event_redis
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  ollama:
    image: ollama/ollama:latest
    container_name: event_ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 10s
      timeout: 10s
      retries: 5

  app:
    image: harshzazadiya/eve_book:v2.0  # Your AI version!
    container_name: event_booking_app
    ports:
      - "8000:8000"
      - "8501:8501"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      ollama:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/EventBooking
      REDIS_URL: redis://redis:6379
      OLLAMA_HOST: http://ollama:11434
      SECRET_KEY: change-this
      ADMIN_SETUP_KEY: change-this
      DEFAULT_ADMIN_NAME: admin
      DEFAULT_ADMIN_EMAIL: admin@event.com
      DEFAULT_ADMIN_PASSWORD: admin123
    volumes:
      - ./uploads:/app/uploads
      - ./vector_store:/app/vector_store
    working_dir: /app
    stdin_open: true
    tty: true

volumes:
  postgres_data:
  ollama_data:
````



## ✅ Step 2 — Run the Application
```bash
docker compose up -d
````
⏱️ First run note : 

The Llama 3.1 8B model (~4.7GB) will be downloaded automatically. This may take 10-30 minutes depending on your internet speed. Subsequent runs will be instant.


## ✅ Step 3 — Access the Application
Service	URL
```bash
Streamlit Frontend      : http://localhost:8501
FastAPI Backend         : http://localhost:8000
API Documentation	    : http://localhost:8000/docs
````

---
## 🔐 Default Admin
```bash
Email     : admin@event.com
Password  : admin123
````

Additional admins can be created via the /admin/create-admin endpoint using the ADMIN_SETUP_KEY.

---

## 💬 Chat with AI Assistant
Once the app is running, navigate to the AI ChatBot tab and start chatting!

Example queries:
```text
"What events are available this weekend?"

"Show me my wallet balance"

"Is food included in the Freshers Party?"

"Book event ID 3 for me"

"Tell me about events hosted by 'harsh'"

"What's in the document for the New Year celebration?"
````

The AI will:
```text
Use tools to check real data when needed

Search documents for specific information

Remember the context of your conversation

Respect your role permissions (users can't do admin actions)
````

---
# 📂 Project Structure
```text
Eve_book/
├── src/
│   ├── AI/
|   |   ├── Tools/
|   |   |   ├── __init__.py
|   |   |   ├── admin_tools.py     # Admin tools for Agent
|   |   |   ├── host_tools.py      # Host tools for Agent
|   |   |   ├── user_tools.py      # User tools for Agent
|   |   |   ├── default_tools.py   # Default tools which can be used by user type of any role
|   |   ├── __init__.py
│   │   ├── graph.py               # LangGraph agent
│   │   ├── RAG.py                 # Vector search
│   │   ├── guardrails.py          # Role permissions
│   │   └── tools/                 # AI tools for each role
│   ├── routers/
│   │   ├── admin.py
│   │   ├── auth.py
│   │   ├── host.py
│   │   └── user.py
│   ├── app.py                     # Streamlit UI
│   ├── main.py                    # FastAPI entry
│   ├── database.py
│   ├── model.py
│   ├── uploads/                   # Event PDFs
|   └── vector_store/              # Vector store of all PDFs in uploads/  [FAISS Index]
├── docker-compose.yaml
├── Dockerfile
└── README.md
````

---

# ⚙️ Environment Variables
Variable	Purpose	Default
```text
DATABASE_URL	            PostgreSQL connection	    postgresql://postgres:postgres@postgres:5432/EventBooking
REDIS_URL	                Redis cache	                redis://redis:6379
OLLAMA_HOST	                Ollama service URL	        http://ollama:11434
SECRET_KEY	                JWT signing	                change-this
ADMIN_SETUP_KEY	            Admin creation key	        change-this-in-production
DEFAULT_ADMIN_EMAIL	        Default admin email	        admin@event.com
DEFAULT_ADMIN_PASSWORD	    Default admin password	    admin123
````

---

# 💰 Wallet Logic
## Booking Flow
User wallet ➜ Deduct ticket price

Host wallet ➜ Receives payment

## Cancellation / Refund Flow
User wallet ➜ Refunded

Host wallet ➜ Deducted

---

# 📸 Screenshots

## User Dashboard
<img width="1919" height="1084" alt="image" src="https://github.com/user-attachments/assets/78390170-4547-4c07-b3c6-359f9140d1e8" />

## Host Dashboard
<img width="1919" height="1088" alt="image" src="https://github.com/user-attachments/assets/ce5b6eb7-d273-4aae-b25a-86974c3549ef" />

## Admin Dashboard
<img width="1918" height="1072" alt="image" src="https://github.com/user-attachments/assets/64759838-0ea0-45af-a547-ec7fafc468f7" />

---

# LOGS

You can see the tool calling of Agent and other requests in terminal 

For example :
```text
INFO:     Will watch for changes in these directories: ['D:\\internship_project\\Eve_book\\src']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [16792] using WatchFiles
🔄 Initializing Ollama...
✅ Ollama ready
🚀 Initializing...
INFO:     Started server process [33084]
INFO:     Waiting for application startup.
==================================================
🚀 Application starting up...
📚 Initializing vector store...
✅ FAISS ready with 6 vectors
✅ Admin user already exists
✅ Startup complete
==================================================
INFO:     Application startup complete.
INFO:     127.0.0.1:60990 - "POST /auth/token HTTP/1.1" 200 OK
INFO:     127.0.0.1:61018 - "GET /auth/me HTTP/1.1" 200 OK
INFO:     127.0.0.1:61075 - "GET /admin/users HTTP/1.1" 200 OK
INFO:     127.0.0.1:61104 - "GET /admin/bookings HTTP/1.1" 200 OK
INFO:     127.0.0.1:61131 - "GET /admin/events HTTP/1.1" 200 OK
INFO:     127.0.0.1:61146 - "GET /chat/threads HTTP/1.1" 200 OK
✅ Created new thread: id=49, owner_id=1, owner_type=admin

============================================================
🤖 Processing: admin (admin, admin, ID: 1)
💬 Thread: 49
💬 Message: show me system stats
============================================================

🛠️ Using: get_system_stats
INFO:     127.0.0.1:61288 - "POST /chat/ask HTTP/1.1" 200 OK
INFO:     127.0.0.1:53126 - "GET /auth/me HTTP/1.1" 200 OK
INFO:     127.0.0.1:53153 - "GET /chat/threads HTTP/1.1" 200 OK

============================================================
🤖 Processing: admin (admin, admin, ID: 1)
💬 Thread: 49
💬 Message: show me all users
============================================================

🛠️ Using: get_all_users
INFO:     127.0.0.1:53178 - "POST /chat/ask HTTP/1.1" 200 OK

````

---

# 🧪 Running Locally (Without Docker)
If you prefer to run without Docker:

## 1. Install Ollama
```bash
curl -fsSL https://ollama.com/install.sh | sh
````

## 2. Pull models
```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
````

## 3. Set up Python environment
```bash
cd src
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
````

## 4. Start services
```bash
 Terminal 1: ollama serve

 Terminal 2: uvicorn main:app --reload
 
 Terminal 3: streamlit run app.py
````

---

## 🤝 Contributing
Contributions are welcome! Feel free to open issues or submit pull requests.

## ⭐ Support
If you find this project useful, please consider giving it a star on GitHub! It helps others discover it.
EOF

---

# 👨‍💻 Author
Harsh Zazadiya


