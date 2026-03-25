# WasteIQ — Setup Guide

---

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 15+

### 1. Database (local)

```bash
createdb wasteiq
psql wasteiq < schema.sql
```

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # edit: set DATABASE_URL and SECRET_KEY
python -m app.ml.trainer       # train base ML model once
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local     # edit: NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

App: http://localhost:3000

---

## Deploying to Vercel

WasteIQ uses **two separate Vercel projects** — one for the frontend (Next.js) and one for the backend (Python serverless).

### Step 1 — Set up the database on Neon (free)

1. Go to https://neon.tech and create a free account
2. Create a new project → choose a region close to your users
3. Copy the **Connection string** (looks like `postgresql://user:pass@host/dbname`)
4. In the Neon SQL editor, paste and run the contents of `schema.sql`

### Step 2 — Push code to GitHub

```bash
cd C:\Users\karth\Documents\mynextidea
git init
git add .
git commit -m "Initial WasteIQ MVP"
# Create a repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/wasteiq.git
git push -u origin main
```

### Step 3 — Deploy the Backend to Vercel

1. Go to https://vercel.com → "Add New Project"
2. Import your GitHub repo
3. Set **Root Directory** to `backend`
4. Framework Preset: **Other**
5. Add these Environment Variables:
   - `DATABASE_URL` → your Neon connection string
   - `SECRET_KEY` → any long random string (e.g. run `openssl rand -hex 32`)
   - `ENVIRONMENT` → `production`
   - `FRONTEND_URL` → leave blank for now (fill in after Step 4)
6. Click **Deploy**
7. Note your backend URL, e.g. `https://wasteiq-api.vercel.app`

### Step 4 — Deploy the Frontend to Vercel

1. Go to https://vercel.com → "Add New Project"
2. Import the same GitHub repo
3. Set **Root Directory** to `frontend`
4. Framework Preset: **Next.js** (auto-detected)
5. Add this Environment Variable:
   - `NEXT_PUBLIC_API_URL` → your backend URL from Step 3
6. Click **Deploy**
7. Note your frontend URL, e.g. `https://wasteiq.vercel.app`

### Step 5 — Link frontend URL back to backend

1. Go to your **backend** Vercel project → Settings → Environment Variables
2. Set `FRONTEND_URL` → your frontend URL from Step 4
3. Redeploy the backend (Deployments → Redeploy)

Your app is now live at your frontend Vercel URL.

---

## Custom Domain (optional)

In Vercel → your frontend project → Settings → Domains → add your domain (e.g. `wasteiq.com`).
Vercel handles SSL automatically.

---

## Using the App

1. Open your Vercel frontend URL
2. Click "Create one free" to register
3. Click "+ New Project" → add materials → "Generate Predictions"
4. After delivery, "Record Actuals" to activate the AI feedback loop

---

## Project Structure

```
mynextidea/
├── backend/
│   ├── api/index.py             # Vercel serverless entry point
│   ├── vercel.json              # Vercel routing config
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py          # NullPool for serverless compatibility
│   │   ├── models/
│   │   │   ├── db_models.py
│   │   │   └── schemas.py
│   │   ├── api/routes/
│   │   │   ├── auth.py
│   │   │   ├── projects.py
│   │   │   ├── predictions.py
│   │   │   └── actuals.py
│   │   └── ml/
│   │       ├── features.py      # Feature engineering (patent-critical)
│   │       ├── predictor.py
│   │       └── trainer.py
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── page.tsx
│   │   ├── login/page.tsx
│   │   ├── signup/page.tsx
│   │   ├── dashboard/page.tsx
│   │   └── projects/
│   │       ├── new/page.tsx
│   │       └── [id]/page.tsx
│   ├── components/
│   │   ├── navbar.tsx
│   │   └── prediction-table.tsx
│   └── lib/
│       ├── api.ts
│       └── auth.ts
├── schema.sql
└── PRODUCT_SPEC.md
```
