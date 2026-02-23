# 🎟 Eve_Book — Event Booking Platform

A full-stack **Event Booking Application** built using **FastAPI**, **PostgreSQL**, **Redis**, and **Streamlit UI** with **Role-Based Authentication**.

This platform allows users to book events, hosts to manage events, and admins to manage the entire system.

---

## 🚀 Features

### 👤 User
- Browse available events  
- Book tickets  
- Cancel bookings  
- Wallet system with top-up support  
- Promote to Host (paid upgrade)

---

### 🏢 Host
- Create events  
- Manage hosted events  
- Delete events  
- Earn money directly into wallet from bookings  

---

### 🛠 Admin
- View all users and hosts  
- View all events  
- View all bookings  
- Delete events and bookings  
- Demote hosts back to users  
- View all wallets and balances  

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

## 🧠 Architecture Highlights

✔ Role Based Authorization  
✔ Redis caching for fast responses  
✔ Wallet transaction system  
✔ Atomic booking & refund logic  
✔ Dockerized micro-service style setup  

---

## 📦 Docker Hub Image

👉 https://hub.docker.com/r/harshzazadiya/eve_book

---

# 🐳 Running the Application (Recommended Way)

This project requires:

- PostgreSQL  
- Redis  
- Eve_Book Backend & UI  

The easiest way to run everything is using **Docker Compose**.

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
version: "3.9"

services:

  postgres:
    image: postgres:16
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

  redis:
    image: redis:7
    container_name: event_redis
    ports:
      - "6379:6379"

  event_app:
    image: harshzazadiya/eve_book:latest
    container_name: event_booking_app
    ports:
      - "8000:8000"
      - "8501:8501"
    depends_on:
      - postgres
      - redis
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/EventBooking
      REDIS_URL: redis://redis:6379
      SECRET_KEY: super-secret-key
      ADMIN_SETUP_KEY: setup_admin_key
      BASE_URL: http://backend:8000

volumes:
  postgres_data:
````

---

## ✅ Step 3 — Run Application

Inside the folder containing `docker-compose.yaml`:

```bash
docker compose up -d
```

---

## ✅ Step 4 — Access the Application
🌐 Backend API

```bash
http://localhost:8000
```

📘 Swagger Docs

```bash
http://localhost:8000/docs
````

🎨 Streamlit UI

```bash
http://localhost:8501
````

---

# 🔐 Creating Admin

There is one by default admin when system starts...
```bash
Username : admin
Password : admin123
```

Then there is endpoint in the Swagger UI where you can add a new admin but you will need a key to make one.

---

# 💰 Wallet Logic
### 🎟 Booking Flow

User wallet ➜ Deduct ticket price
Host wallet ➜ Receives payment


### ❌ Booking Cancellation / Admin Deletion

User wallet ➜ Refunded
Host wallet ➜ Deducted

---

📂 Project Structure
```bash
routers/
 ├── admin.py
 ├── auth.py
 ├── host.py
 └── user.py

app.py           -> Streamlit UI  
main.py          -> FastAPI app entry  
database.py      -> DB config  
model.py         -> SQLAlchemy models  
start.sh         -> Container startup script  
Dockerfile  
docker-compose.yaml  
```
---

## ⚙ Environment Variables
| Variable |	Purpose |
|----------|----------------------|
| DATABASE_URL |	PostgreSQL connection |
| REDIS_URL |	Redis cache |
| SECRET_KEY |	JWT signing |
| ADMIN_SETUP_KEY |	Admin creation key |
| BASE_URL |	Backend service URL |

---

## 📸 Screenshots
USER DASHBOARD

<img width="1919" height="1092" alt="Screenshot 2026-02-09 152621" src="https://github.com/user-attachments/assets/a6093c5c-82cc-4973-996a-46067baa5de5" />

HOST DASHBOARD

<img width="1919" height="1088" alt="Screenshot 2026-02-09 152521" src="https://github.com/user-attachments/assets/ca2609e1-0c94-406f-9a27-fa30ec8003ce" />

ADMIN DASHBOARD

<img width="1914" height="1084" alt="Screenshot 2026-02-09 152649" src="https://github.com/user-attachments/assets/fdc13309-93a2-4124-b732-9f876f6f4db6" />


---

# 👨‍💻 Author

Harsh Zazadiya

## 🔗 GitHub

```bash
https://github.com/HarshZazadiya
```

## 🐳 DockerHub

```bash
https://hub.docker.com/r/harshzazadiya/eve_book
```

