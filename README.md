# 🎟  EveBook — AI-Powered Event Booking Platform

EveBook is a full-stack event booking platform with an integrated AI assistant. It is built with **FastAPI** (backend), **Streamlit** (frontend), and **PostgreSQL** (database with pgvector). The AI layer is powered by **LangGraph**, **Groq (Kimi K2)**, **FAISS**, and a local **MCP server** for file-system operations.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Database Models](#database-models)
- [API Endpoints](#api-endpoints)
- [AI System](#ai-system)
- [MCP File Server](#mcp-file-server)
- [Environment Variables](#environment-variables)
- [Setup & Running](#setup--running)
- [Role System](#role-system)

---

## 🚀 Architecture Overview

```
┌──────────────────────────────────────────────────┐
│               Streamlit Frontend (app.py)        │
│  Auth · User Dashboard · Host Dashboard · Admin  │
│  AI Chat · HITL Approval UI                      │
└──────────────────────┬───────────────────────────┘
                       │ HTTP (localhost:8000)
┌──────────────────────▼────────────────────────────┐
│              FastAPI Backend (main.py)            │
│  /auth  /user  /host  /admin  /chat  /default     │
└─────┬───────────────────────────────────┬─────────┘
      │                                   │
  PostgreSQL                        LangGraph Agent
  (pgvector)                        + Groq Kimi K2
  SQLAlchemy                        + FAISS RAG
                                    + MCP (SSE :8001)
```

---

## 🚀 Features

### Platform

- **User registration and login** for users (username + password) and hosts (email + password)
- **JWT authentication** — separate tokens for users, hosts, and admins; role encoded in token
- **Wallet system** — each user and host has a wallet; top-up, deduct, and refund are all transactional
- **Event booking** — users browse available events, book with a single click (wallet deducted), cancel for a full refund
- **Host promotion** — a user can pay ₹10,000 from their wallet to become a host; admin can demote hosts back
- **Event management** — hosts create, edit, and delete events; each event can have an attached PDF document
- **PDF documents** — event PDFs are stored in `uploads/` and served as static files; both the UI and the AI chatbot can reference them
- **Admin dashboard** — full visibility into users, hosts, events, bookings, wallets, transactions, promotions, and platform stats

## 🧠 AI Chatbot (all roles)

- **Persistent multi-turn conversations** — threads are stored in PostgreSQL; the LangGraph checkpointer keeps full graph state per thread
- **Thread management** — create new conversations, rename threads, delete threads, load chat history
- **Role-aware tool access** — the agent dynamically receives only the tools that match the logged-in user's role
- **RAG (Retrieval-Augmented Generation)** — event PDFs are chunked and indexed in FAISS; the agent can search them to answer questions not covered by structured data
- **Long-term memory** — after each conversation turn, an extractor subgraph runs Llama-3.3-70b to identify and persist user preferences, facts, and goals into a `memories` table backed by pgvector; relevant memories are injected into every future turn
- **Conversation summarization** — when the token count of a thread exceeds 3,500 tokens, a summarizer subgraph condenses older messages and removes them from the graph state while preserving context in a summary string
- **Human-in-the-Loop (HITL) approval** — users can mark any tool as "sensitive"; when the agent wants to call a sensitive tool it pauses via `langgraph.interrupt()`, the frontend shows an approval widget, and the graph resumes only after the user confirms or cancels
- **HITL settings UI** — each role has a dedicated settings tab to configure which tools require approval; defaults include `delete_file`, `delete_pdf`, `change_directory`, and `top_up_wallet`
- **MCP tool integration** — the agent connects to a local FastMCP server over SSE to access a full file-system toolkit

---

## ⚡ Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI + Uvicorn |
| Frontend | Streamlit |
| Database | PostgreSQL 16 with pgvector extension (`ankane/pgvector`) |
| ORM | SQLAlchemy 2.x |
| AI Orchestration | LangGraph 1.x |
| LLM (main agent) | Groq — `moonshotai/kimi-k2-instruct` |
| LLM (extractor & summarizer) | Groq — `llama-3.3-70b-versatile` |
| Embeddings | HuggingFace `sentence-transformers/all-MiniLM-L6-v2` (CPU) |
| Vector Store | FAISS (disk-persisted, rebuilt fresh on startup) |
| Graph Checkpointer | `AsyncPostgresSaver` (LangGraph Postgres checkpointer) |
| Memory Search | pgvector cosine distance |
| MCP Server | FastMCP over SSE |
| PDF Generation | ReportLab |
| PDF Parsing | pypdf / PyPDFLoader |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Observability | LangSmith tracing |

---

## 📂 Project Structure

```
src/
├── main.py                   # FastAPI app, lifespan (startup/shutdown)
├── app.py                    # Streamlit frontend
├── model.py                  # SQLAlchemy ORM models
├── database.py               # Engine + SessionLocal
├── requirements.txt
├── Dockerfile
├── docker-compose.yaml       # PostgreSQL (pgvector) service
├── start.sh
├── wait_ollama.sh
├── uploads/                  # Uploaded event PDFs (served as static files)
├── vector_store/             # FAISS index (built at startup, deleted at shutdown)
├── routers/
│   ├── auth.py               # /auth — login, register user/host
│   ├── user.py               # /user — events, bookings, promote-to-host
│   ├── host.py               # /host — event CRUD, document upload
│   ├── admin.py              # /admin — platform management
│   ├── chatbot.py            # /chat — AI chat, threads, HITL, settings
│   └── default.py            # /default — wallet (shared by all roles)
└── AI/
    ├── RAG.py                # FAISS vector store, LLM + embeddings init, search_documents tool
    ├── graph.py              # LangGraph graph definition, agent node, HITL logic, run_agent()
    ├── mcp_manager.py        # MultiServerMCPClient connecting to :8001/sse
    ├── user_config.py        # Per-user sensitive tool settings (UserSettings table)
    ├── tools/
    │   ├── user_tools.py     # Tools available to users
    │   ├── host_tools.py     # Tools available to hosts
    │   ├── admin_tools.py    # Tools available to admins
    │   └── default_tools.py  # Tools available to all roles (wallet)
    ├── utils/
    │   ├── state.py          # AgentState TypedDict
    │   └── memories.py       # search_memory(), store_memory(), delete_memory()
    ├── subgraphs/
    │   ├── extractor_graph.py   # Memory extraction subgraph (Llama-3.3-70b)
    │   └── summarizer_graph.py  # Conversation summarization subgraph (Llama-3.3-70b)
    └── local_mcp/
        ├── main.py
        ├── pyproject.toml
        └── file_handle/
            └── file_handling_server.py   # FastMCP filesystem server
```

---

## 📂 Database Models

| Table | Description |
|---|---|
| `users` | Platform users (user, host, admin roles) |
| `hosts` | Host profiles linked to a `users` row |
| `events` | Events created by hosts; includes `document_path` and `document_processed` |
| `bookings` | User–event booking records |
| `booking_payments` | Payment record per booking |
| `hosting_payments` | ₹500 fee per event creation |
| `host_promotions` | Records of user→host promotion (₹10,000 fee) |
| `wallets` | Wallet per owner (`user`, `host`, or `admin`) |
| `chat_threads` | Chat thread per user/role with optional custom name |
| `chat_messages` | Individual messages in a thread (role + content) |
| `user_settings` | Per-user HITL sensitive tool list (JSON column) |
| `memories` | Long-term user memories with 384-dim pgvector embedding |

---

## 📂 API Endpoints

### Auth — `/auth`

| Method | Path | Description |
|---|---|---|
| POST | `/auth/token` | Login (user or host); returns JWT |
| POST | `/auth/user` | Register a new user |
| POST | `/auth/host` | Register a new host |
| GET | `/auth/me` | Return current identity from token |

### User — `/user`

| Method | Path | Description |
|---|---|---|
| GET | `/user/` | Get own profile |
| GET | `/user/events` | Browse all available events |
| POST | `/user/event/{event_id}` | Book an event |
| GET | `/user/myEvents` | Get own bookings |
| DELETE | `/user/booking/{booking_id}` | Cancel a booking (refund issued) |
| POST | `/user/promote-to-host` | Pay ₹10,000 and become a host |

### Host — `/host`

| Method | Path | Description |
|---|---|---|
| GET | `/host/` | Get host profile |
| GET | `/host/events` | Get own events |
| POST | `/host/event` | Create event (with optional PDF upload) |
| PUT | `/host/event/{event_id}` | Update event details |
| DELETE | `/host/event/{event_id}` | Delete event (refunds all bookings) |
| PUT | `/host/event_document/{event_id}` | Replace event PDF document |

### Admin — `/admin`

| Method | Path | Description |
|---|---|---|
| GET | `/admin/users` | List all users |
| GET | `/admin/hosts` | List all hosts |
| GET | `/admin/events` | List all events |
| GET | `/admin/bookings` | List all bookings |
| GET | `/admin/wallets` | List all wallets |
| GET | `/admin/promotions` | List host promotion records |
| GET | `/admin/hosting-transactions` | Hosting fee transaction history |
| GET | `/admin/stats` | Platform-wide stats |
| DELETE | `/admin/booking/{booking_id}` | Delete any booking with refund |
| DELETE | `/admin/event/{event_id}` | Delete any event with refunds |
| POST | `/admin/demote-host/{host_id}` | Demote host back to user |

### Chat — `/chat`

| Method | Path | Description |
|---|---|---|
| POST | `/chat/ask` | Send a message or resume HITL (pass `human_approval`) |
| GET | `/chat/threads` | List all threads for current user |
| GET | `/chat/threads/{id}/messages` | Get all messages in a thread |
| DELETE | `/chat/threads/{id}` | Delete a thread |
| PATCH | `/chat/threads/{id}/rename` | Rename a thread |
| GET | `/chat/settings/hitl` | Get current HITL tool list |
| POST | `/chat/settings/hitl` | Update HITL tool list |
| GET | `/chat/tools` | List all tools available to the current role |

### Default — `/default`

| Method | Path | Description |
|---|---|---|
| GET | `/default/myWallet` | Get own wallet balance |
| POST | `/default/topUp` | Add money to wallet |

### Misc

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check (FAISS status) |
| GET | `/uploads/{filename}` | Serve uploaded PDFs as static files |

---

## 🧠 AI System

### LangGraph Agent Graph

The agent graph runs per-request and persists state to PostgreSQL via `AsyncPostgresSaver`.

```
    memory_retriever_node
             │
         agent_node  ◄───────────────────────┐
             │                               │
     ┌─────▼───────┐                         │ 
     │ tool calls? │                         │
┌───►│  yes / no   │                         │
│    └───┬──────┬──┘                         │
│        │      │                            │
│      tools   checker_node                  │
└────────┘      │ (token check)              │
                ▼                            │
           summarizer_graph (if needed) ─────│
                │                            │
           extractor_graph ──────────────────┘
                │
                │
                ▼
               END
```

## Nodes

- `memory_retriever_node` — runs a pgvector similarity search against the `memories` table for the current query; injects up to 2 matching memories into context
- `agent_node` — binds the LLM to all role-appropriate tools, injects system prompt + summary + memories, calls Kimi K2; if a sensitive tool is requested, calls `langgraph.interrupt()` and waits for `Command(resume=...)`
- `tool_node` — executes tool calls; automatically injects `authenticated_user_id` and `authenticated_user_type` for tools that declare those parameters in their schema
- `checker_node` — counts approximate tokens in the message list; if over 3,500 tokens and more than 10 messages, delegates to the summarizer subgraph
- `extractor_node` — delegates to the extractor subgraph to persist new memories

## ❌ HITL Flow

1. User sends a message
2. Agent decides to call a tool that is in the user's sensitive tool list
3. `interrupt()` pauses the graph; the API returns `hitl_required: true` to the frontend
4. Streamlit shows an approval widget
5. User clicks Yes or No
6. Frontend POSTs back to `/chat/ask` with `human_approval: "yes"` or `"no"` and the original message
7. Backend calls `graph.ainvoke(Command(resume=...))` to resume the graph from the exact interrupt point

## 🔗 RAG Pipeline

On startup, `build_fresh_vector_store()` scans `uploads/` for all PDFs, loads and chunks them (`chunk_size=300, overlap=30`), tags each chunk with `event_id` extracted from the filename convention `{host_id}_{event_id}_{title}.pdf`, and builds a FAISS index. The index is deleted on shutdown.

When a host creates or updates an event, the new PDF is immediately added to the live FAISS index via `add_document_to_store()`. When an event is deleted, `delete_event_documents()` rebuilds the index without that event's chunks.

The agent has access to `search_event_documents(query)` which performs a similarity search and returns the top 3 chunks with event ID and source file metadata.

## 🧠 Memory System

After each completed turn, the extractor subgraph sends the last 10 messages to `llama-3.3-70b-versatile` with a structured output schema (`ExtractedMemory`). Extracted memories are typed as `preference`, `personal/fact`, `goal`, or `habit` and stored with a 384-dim embedding (MiniLM). On each subsequent turn, `search_memory()` retrieves the top 2 semantically similar memories via pgvector cosine distance and injects them silently into the agent's context.

## ⚡Available Tools by Role

**All roles (default_tools):**
- `get_wallet_balance` — check wallet balance
- `top_up_wallet` — add money to wallet

**User tools:**
- `get_user_profile` — own profile
- `get_all_available_events` — list all events
- `get_user_bookings` — own bookings with document links
- `book_event_for_user` — book an event (deducts from wallet)
- `cancel_user_booking` — cancel and get refund
- `promote_user_to_host` — pay ₹10,000, become host

**Host tools:**
- `get_host_info` — own host profile (Redis-cached)
- `get_host_events` — own events (Redis-cached)
- `create_host_event` — create event, pay ₹500 fee, auto-generate PDF
- `delete_host_event` — delete event, refund all bookings, restore hosting fee
- `update_host_event` — update event details, regenerate PDF, refresh FAISS
- `update_event_document` — replace event PDF

**Admin tools:**
- `get_all_users`, `get_all_hosts`, `get_all_events`, `get_all_bookings`, `get_all_wallets`, `get_all_promotions`
- `get_all_booking_transactions`, `get_all_hosting_transactions`
- `get_system_stats`
- `delete_event_by_id`, `delete_booking_by_id`
- `demote_host_by_id` — cancels all host events, refunds bookings, transfers wallet
- `promote_to_admin` — requires `ADMIN_SETUP_KEY`

**RAG tool (all roles):**
- `search_event_documents` — semantic search over uploaded event PDFs

**MCP tools (all roles, via local MCP server):**
- `current_directory`, `change_directory`, `list_files`
- `read_file`, `create_file`, `update_file`, `delete_file`
- `create_pdf`, `update_pdf`, `file_info`

---

## 🛠 MCP File Server

The local MCP server runs as a separate process on `http://127.0.0.1:8001/sse` using FastMCP with SSE transport.

**Source:** `AI/local_mcp/file_handle/file_handling_server.py`

The server exposes a sandboxed workspace directory. It handles:
- Base64 auto-detection and decoding for binary files
- PDF text extraction via pypdf
- PDF creation and append/prepend/replace updates via ReportLab
- Plain text file CRUD

The main application connects via `langchain-mcp-adapters` (`MultiServerMCPClient`). Tools are fetched once and cached.

To start the MCP server (from `AI/local_mcp/`):

```bash
uv run python file_handle/file_handling_server.py
```

---

## Environment Variables

Create a `.env` file in `src/`:

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/EventBooking

# Redis (optional — used for host tool caching)
REDIS_URL=redis://localhost:6379/0

# JWT
SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Default admin (created automatically on first startup if no admin exists)
DEFAULT_ADMIN_NAME=admin
DEFAULT_ADMIN_EMAIL=admin@event.com
DEFAULT_ADMIN_PASSWORD=admin123

# Admin promotion key
ADMIN_SETUP_KEY=your_admin_setup_key

# Groq API
GROQ_API_KEY=your_groq_api_key

# LangSmith (optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=eve_book
```

---

## ✅ Setup & Running

### 1. Start PostgreSQL (with pgvector)

```bash
docker compose up -d
```

This starts `ankane/pgvector` on port **5433**.

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the MCP file server

```bash
cd src/AI/local_mcp/file_handle
uv run python file_handle/file_handling_server.py
```

Runs on `http://127.0.0.1:8001/sse`.

### 4. Start the FastAPI backend

```bash
cd src
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

On startup the application will:
- Build a fresh FAISS index from all PDFs in `uploads/`
- Initialize the async Postgres checkpointer (creates LangGraph checkpoint tables)
- Create the default admin user and wallet if they do not exist

### 5. Start the Streamlit frontend

```bash
cd src
streamlit run app.py
```

Runs on `http://localhost:8501`.

---

## 🛠 Role System

| Role | How obtained | Key capabilities |
|---|---|---|
| `user` | Registration via `/auth/user` | Browse events, book, cancel, top up wallet, chat |
| `host` | Registration via `/auth/host` or user promotion (₹10,000) | Create/edit/delete own events, upload PDFs, chat |
| `admin` | Created automatically on startup or promoted via `promote_to_admin` tool | Full platform management, demote hosts, view all data |

Hosts authenticate with their **email** (not username). Users authenticate with their **username**. The login endpoint tries user authentication first, then host authentication.

JWT tokens encode `id`, `type` (`user` or `host`), and `role` (`user`, `host`, or `admin`). The chatbot extracts all three to determine which tools to load and how to resolve names.

---

## 👨‍💻 Notes

- The FAISS index is rebuilt from scratch on every startup and deleted on shutdown. It is not persisted between runs; all PDFs must remain in `uploads/` for RAG to work.
- Redis is optional. If `REDIS_URL` is not set, host tool caching is simply disabled and operations fall back to direct database queries.
- The `docker-compose.yaml` currently runs only PostgreSQL. Redis and any other services must be run separately.
- The conversation checkpointer uses the same PostgreSQL database as the application. LangGraph will create its own internal tables (`checkpoints`, etc.) on first run via `checkpointer.setup()`.
- Hosting fee is ₹500 per event creation. Promotion fee is ₹10,000. Both flow into the admin wallet.