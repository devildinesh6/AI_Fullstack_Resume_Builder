## AI Career Intelligence Platform (Minimal)

Minimal full-stack Career Intelligence Assistant:
- **Frontend**: React (Vite) chat UI + resume preview panel (text-only)
- **Backend**: Python FastAPI + LangGraph (intent routing + step-by-step data collection)
- **DB**: Supabase Postgres (`career_sessions` table)
- **Webhook**: POST structured results once required fields are collected and AI output is generated

### 1) Supabase table

Run this SQL in Supabase:

```sql
create table if not exists public.career_sessions (
  id uuid primary key default gen_random_uuid(),
  session_id text not null,
  full_name text,
  agent_type text not null check (agent_type in ('resume','job_prediction')),
  user_data jsonb not null default '{}'::jsonb,
  ai_output jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  webhook_sent boolean not null default false
);

create index if not exists idx_career_sessions_session_id
  on public.career_sessions (session_id);
```

### 2) Backend setup

Create `backend/.env` from `backend/.env.example`.

```bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3) Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Frontend dev server defaults to `http://localhost:5173` and calls the backend at `http://localhost:8000`.

