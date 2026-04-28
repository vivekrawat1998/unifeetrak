# UniFeeTrak — University Fee Management System

A single-page web application for tracking monthly university fees.  
**Stack:** Flask · PostgreSQL · Vanilla JS · HTML/CSS

---

## Project Structure

```
unifeetrak/
├── app.py                  Flask application factory + gunicorn entry point
├── requirements.txt        Python dependencies (includes gunicorn)
├── render.yaml             Render.com one-click deploy config
├── .env.example            Copy → .env for local development
├── .gitignore
│
├── database/
│   ├── db.py               PostgreSQL connection + init_db + seed_db
│   ├── schema.sql          CREATE TABLE statements (idempotent)
│   └── seed.sql            Demo data (skipped if students already exist)
│
├── routes/
│   ├── student.py          Blueprint: /api/students/…
│   └── fees.py             Blueprint: /api/fees/…
│
└── static/
    ├── index.html          Single-page frontend (pure HTML)
    ├── css/
    │   └── style.css       All styles
    └── js/
        └── app.js          All JavaScript (no frameworks)
```

---

## Option 1 — Deploy to Render (FREE, Recommended)

Render gives you a free PostgreSQL database + free web service with zero config.

### Step 1 — Set up your project folder correctly

Make sure your project looks exactly like the structure above before pushing to GitHub.

### Step 2 — Push to GitHub

```bash
# Inside your project folder
git init
git add .
git commit -m "Initial commit"

# Create a new repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/unifeetrak.git
git push -u origin main
```

### Step 3 — Deploy on Render

1. Go to **[https://dashboard.render.com](https://dashboard.render.com)**
2. Sign up / log in (free account)
3. Click **New → Blueprint**
4. Connect your GitHub account and select your `unifeetrak` repository
5. Render reads `render.yaml` automatically — click **Apply**
6. Wait ~3 minutes for the build to finish
7. Your live URL will be: `https://unifeetrak.onrender.com` (or similar)

> **That's it.** The database is created, environment variables are wired, and the app starts automatically.

### Step 4 — Seed your database (first time only)

After deploy, go to your Render dashboard → **unifeetrak** service → **Shell** tab, and run:

```bash
python -c "from database.db import init_db, seed_db; init_db(); seed_db()"
```

Or upload your CSVs directly through the UI once the app is live.

---

## Option 2 — Run Locally

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ running locally
- Git

### Step 1 — Clone and set up

```bash
git clone https://github.com/YOUR_USERNAME/unifeetrak.git
cd unifeetrak

# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2 — Configure environment

```bash
cp .env.example .env
```

Open `.env` and set your local PostgreSQL credentials:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=unifeetrak
DB_USER=postgres
DB_PASSWORD=your_password_here
```

### Step 3 — Create the database

In psql or pgAdmin, create the database:

```sql
CREATE DATABASE unifeetrak;
```

### Step 4 — Run the app

```bash
python app.py
```

Open **[http://localhost:5000](http://localhost:5000)** in your browser.

The app will:
- Create all tables automatically (`init_db`)
- Seed demo data if the database is empty (`seed_db`)

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/students?month=&year=&batch_year=` | All students with fee status for the period |
| GET | `/api/students/batches?year=` | Distinct batch names (filtered by intake year) |
| GET | `/api/students/semesters?batch=` | Distinct semesters |
| POST | `/api/students/upload` | Upload students CSV |
| GET | `/api/fees/stats?month=&year=&batch_year=` | Stat card aggregates |
| POST | `/api/fees/upload` | Upload fees CSV |
| GET | `/api/fees/export?month=&year=&batch=&status=` | Download filtered CSV |

---

## CSV Upload Format

### Students CSV

```csv
name,roll_number,batch_name,semester
Aarav Sharma,CSE25001,2025 – Aug - B.Tech CSE,B.Tech CSE – Sem 1
Priya Singh,CSE25002,2025 – Aug - B.Tech CSE,B.Tech CSE – Sem 2
```

### Fees CSV

```csv
roll_number,month,year,amount_paid,payment_date
CSE25001,4,2026,15000,2026-04-10
CSE25002,4,2026,15000,
```

> Upload students first, then fees. `payment_date` is optional — defaults to today if blank.

---

## Reset Database

To wipe everything and start fresh, run in psql:

```sql
TRUNCATE TABLE fees     RESTART IDENTITY CASCADE;
TRUNCATE TABLE students RESTART IDENTITY CASCADE;
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| CSS not loading | Check `href="/static/css/style.css"` in `index.html` (needs leading `/`) |
| `updated_at` column error on fees upload | Run `migrate_add_updated_at.sql` in your DB |
| Year filter shows all students | Make sure you're using the latest `student.py` with `batch_year` support |
| Render build fails | Check Python version is set to `3.11.0` in render.yaml |
| Free Render DB expires | Render free PostgreSQL expires after 90 days — upgrade or recreate |