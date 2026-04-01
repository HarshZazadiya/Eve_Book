# 🎟 EveBook — AI-Powered Event Booking + Automation Platform

EveBook is a **production-style full-stack event booking system** combined with a **LangGraph-based AI agent** and **workflow automation engine**.

This project goes beyond CRUD — it integrates:
- 🤖 AI agents with memory + tool execution  
- 🔄 Event-driven automation workflows (n8n webhooks)  
- 📄 RAG over event documents  
- 🧠 Persistent user memory  
- 🔌 MCP server for file system operations  

---

## 🚀 What This Project Actually Solves


This system goes further than :
> "User books event → Done"

- Automatically trigger workflows on events  
- Let AI **take actions (not just chat)**  
- Maintain **long-term user context**  
- Enable **real automation pipelines**

---

## 🏗 Architecture Overview
```bash
Frontend (Streamlit)
         │
         ▼
FastAPI Backend (REST APIs)
 │
 ├── PostgreSQL (pgvector)
 ├── LangGraph AI Agent
 │ ├── Groq LLM (Kimi K2)
 │ ├── Memory (pgvector)
 │ ├── RAG (FAISS)
 │ └── Tool Execution
 │
 ├── MCP Server (File System via SSE)
 │
 └── Workflow Engine (Webhook-based)
```


---

## ⚡ Core Systems

### 1️⃣ Event Booking Platform

- JWT authentication (User / Host / Admin)
- Wallet system (top-up, refund, transactions)
- Event booking & cancellation
- Host promotion (₹10,000 one time payment)
- Event management with PDF support and Google Sheet of users
- Admin dashboard (full control)

---

### 2️⃣ AI Agent System (LangGraph)

This is the **brain of the system**.

#### Features:
- Multi-turn conversations
- Role-based tool access
- Memory injection (pgvector)
- RAG over event PDFs
- Tool calling (real actions)
- Subgraphs for:
  - Memory extraction
  - Conversation summarization

---

### 🧠 AI Flow
```bash
        User Query
            ↓
Memory Retrieval (pgvector)
            ↓
Agent Decision (LLM + tools)
            ↓
 Tool Execution (if needed)
            ↓
HITL Approval (if sensitive)  →  If Yes then trigger n8n Automation
            ↓
  Summarization (if long) 
            ↓
       Memory Storage
```


---

### 3️⃣ 🧠 Memory System

- Extracts:
  - Preferences
  - Goals
  - Facts
  - Habits

- Stored as embeddings (pgvector)
- Automatically reused in future conversations

---

### 4️⃣ 📄 RAG System

- Event PDFs → chunked → embedded
- Stored in FAISS
- Queried dynamically during chat

---

### 5️⃣ ⚠ Human-in-the-Loop (HITL)

Sensitive actions require approval:

Examples:
- delete_file
- wallet operations
- file system changes

Flow:
1. Agent pauses
2. UI asks user
3. Execution resumes

---

## 🔄 6️⃣ Workflow Automation System (IMPORTANT)

This is one of the most powerful parts of your project.

The system supports **webhook-triggered workflows** (tested via `n8n_test.py`).

### Supported Automations:

- ✅ Booking → Email + Google Sheet entry  
- ✅ Booking Update → Notification  
- ✅ New User/Host → Welcome email  
- ✅ Promotion → Trigger workflow  
- ✅ Host Event → Spreadsheet tracking  
- ✅ Delete Booking → Remove from sheet  
- ✅ Delete Event → Cleanup  

👉 This enables **real-world automation pipelines**, not just backend logic.

---

## 🔌 7️⃣ MCP Server (File System AI Control)

Located in:
```bash
AI/local_mcp/file_handle/
```


Capabilities:
- File CRUD
- PDF read/write/update
- Directory navigation
- Base64 file handling

Runs on:
```bash
http://127.0.0.1:8001/sse
```


---

## 🛠 Tech Stack

| Layer | Tech |
|------|------|
| Backend | FastAPI |
| Frontend | Streamlit |
| Database | PostgreSQL + pgvector |
| ORM | SQLAlchemy |
| AI Framework | LangGraph |
| LLM | Groq (Kimi K2, Llama 3.3) |
| Vector Store | FAISS |
| Memory | pgvector |
| Automation | Webhooks |
| File AI | MCP Server |
| PDF | ReportLab + pypdf |
| Auth | JWT + bcrypt |

---

## 📂 Project Structure
```bash
src/
├── AI/
│   └── local_mcp/
│   │   ├── main.py
│   │   ├── pyproject.toml
│   │   └── file_handle/
│   │       └── file_handling_server.py   # FastMCP filesystem server
│   ├── tools/
│   │   ├── user_tools.py                 # Tools available to users
│   │   ├── host_tools.py                 # Tools available to hosts
│   │   ├── admin_tools.py                # Tools available to admins
│   │   └── default_tools.py              # Tools available to all roles (wallet)
│   ├── utils/
│   │   ├── state.py                      # AgentState TypedDict
│   │   └── memories.py                   # search_memory(), store_memory(), delete_memory()
│   ├── subgraphs/
│   │   ├── extractor_graph.py            # Memory extraction subgraph (Llama-3.3-70b)
│   │   └── summarizer_graph.py           # Conversation summarization subgraph (Llama-3.3-70b)
│   ├── RAG.py                            # FAISS vector store, LLM + embeddings init, search_documents tool
│   ├── graph.py                          # LangGraph graph definition, agent node, HITL logic, run_agent()
│   ├── mcp_manager.py                    # MultiServerMCPClient connecting to :8001/sse
│   └── user_config.py                    # Per-user sensitive tool settings (UserSettings table)
├── routers/
│   ├── auth.py                           # /auth — login, register user/host
│   ├── user.py                           # /user — events, bookings, promote-to-host
│   ├── host.py                           # /host — event CRUD, document upload
│   ├── admin.py                          # /admin — platform management
│   ├── chatbot.py                        # /chat — AI chat, threads, HITL, settings
│   └── default.py                        # /default — wallet (shared by all roles)
├── uploads/                              # Uploaded event PDFs (served as static files)
├── vector_store/                         # FAISS index (built at startup, deleted at shutdown)
├── main.py                               # FastAPI app, lifespan (startup/shutdown)
├── app.py                                # Streamlit frontend
├── model.py                              # SQLAlchemy ORM models
├── database.py                           # Engine + SessionLocal
├── requirements.txt
├── Dockerfile
├── docker-compose.yaml                   # PostgreSQL (pgvector) service
├── start.sh
└── wait_ollama.sh

```


---

## 🔌 API Overview

### Auth
- `/auth/token`
- `/auth/user`
- `/auth/host`

### User
- Browse events
- Book / cancel
- Promote to host

### Host
- Manage events
- Upload documents

### Admin
- Full system control

### Chat (AI)
- `/chat/ask`
- `/chat/threads`
- `/chat/settings`

---

## 🛠 Setup (Realistic)

### 1. Start Database
```bash
docker compose up -d
```
### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Start MCP Server
```bash
cd src/AI/local_mcp/file_handle
uv run python file_handling_server.py
```

### 4. Backend
```bash
uvicorn main:app --reload
```

### 5. Start Frondend
```bash
streamlit run app.py
```

---
## 👨‍💻 Roles

|  Role |  Capabilities |
|-------|---------------|
| User  |  Book events  |
| Host  | Manage events |
| Admin |  Full control |


## 📌 Important Notes
- FAISS index rebuilds on startup
- MCP runs separately
- Redis is optional
- PostgreSQL stores AI + app state
  

## 🌟 Why This Project Stands Out

This is not a basic project. It demonstrates:

- AI agents that take actions
- Real memory + RAG integration
- Workflow automation (industry-level use case)
- Clean backend architecture
- Tool-based AI system (LangGraph)

 
---
### ⭐ Give it a star if you found it useful!