# CivicFix

**AI-powered civic issue reporting, verification, prioritisation, routing, tracking, resolution, and municipal intelligence platform.**

## Problem

Citizens report civic issues (potholes, garbage, broken streetlights, drainage, sewage, water leaks, fallen trees, traffic signals, and dozens more) through phone calls, social media, and disconnected municipal systems. Reports get lost, duplicated, misrouted, or receive no clear priority — and citizens have no visibility into what happens after they report. Municipal staff lack one consolidated dashboard, a live map, priority queues, or reliable proof that something was actually fixed.

## Solution

CivicFix is a single, cohesive platform that takes a civic report from a citizen's phone all the way to verified resolution:

1. **Citizen reports** any civic problem (photo + GPS + short description) — in English or Tamil, online or fully **offline** (saved to IndexedDB, auto-synced when connectivity returns).
2. **Backend pipeline** runs the report through: idempotency check → spam/authenticity scoring → AI issue classification → duplicate detection (merges repeat reports into one Issue) → severity assessment → location-risk assessment (proximity to schools/hospitals/etc.) → transparent 0–100 priority scoring → automatic department routing → human-readable complaint ID.
3. **Municipal staff** get a live command-center dashboard: KPIs, a Leaflet/OpenStreetMap live map, filterable priority queues, a manual review queue for suspicious reports, and a full issue detail/action workflow (accept → start work → **mandatory before/after resolution evidence** → awaiting citizen verification).
4. **Citizen verification**: the citizen sees before/after photos and confirms **Fixed** or **Still Broken** — a "no" reopens the issue and boosts its priority.
5. **Analytics**: department response/resolution time, SLA/backlog/overdue tracking, and **recurring hotspot detection** (clusters of repeat reports) surfaced as a planning insight for infrastructure teams.

## Features

- Multi-category civic issue taxonomy (40+ issue types across Roads, Waste, Electrical, Drainage, Sewerage, Water, Traffic, Parks, Sanitation, Animal Welfare, Enforcement, and more) — extensible via a single config file, no code rewrite needed.
- Mandatory offline reporting: IndexedDB persistence, `client_report_id` idempotency, automatic background sync, PWA installable app shell.
- Deterministic AI fallback (`AI_PROVIDER=mock`) so the whole pipeline — classification, spam detection, severity, routing — works with **zero external API keys**, and never breaks the demo.
- Spam/authenticity scoring with an explainable breakdown, feeding a staff-reviewable **Manual Review Queue** (never silent deletion).
- Duplicate detection: `Issue` (one real-world problem) vs `IssueReport` (one citizen's report) — many reports, one issue, growing reporter count.
- Transparent priority engine (severity 35% / reporter count 20% / location importance 20% / issue age 15% / safety impact 10%), fully visible to staff.
- Full status workflow with `StatusHistory` audit trail, in-app notifications, SLA/overdue flags, department performance analytics, and hotspot clustering.
- English + Tamil citizen UI via a translation-dictionary i18n layer, with voice input where the browser supports Speech Recognition.

## Architecture

```
Citizen (PWA) ──online──► FastAPI ──► Idempotency ──► Spam/Auth ──► Duplicate Detection
     │                                                                     │
   offline──► IndexedDB ──(auto-sync)──┘                          AI Classification
                                                                           │
                                                                  Severity + Location Risk
                                                                           │
                                                                    Priority Engine
                                                                           │
                                                                  Department Routing
                                                                           │
                                                                        SQLite
                                                                    ┌──────┴──────┐
                                                          Citizen Tracking   Staff Dashboard
                                                          + Notifications    + Live Map + Workflow
                                                                    └──────┬──────┘
                                                              Resolution Evidence
                                                                           │
                                                              Citizen Verification
                                                                           │
                                                          Resolved / Reopened → Analytics + Hotspots
```

## Tech Stack

- **Frontend**: React, Vite, TypeScript, Tailwind CSS, React Router, Zustand, Leaflet/OpenStreetMap, `idb` (IndexedDB), `vite-plugin-pwa`.
- **Backend**: Python, FastAPI, SQLAlchemy, Pydantic, SQLite (swap `DATABASE_URL` for PostgreSQL later — no code changes needed), JWT auth (`python-jose`), `passlib` password hashing.
- **AI Layer**: modular services (`ai_classifier`, `spam_detector`, `duplicate_detector`, `priority_engine`, `routing_service`, `hotspot_service`, `location_service`) with a deterministic mock mode as the default/fallback.

## Setup

### Backend

```bash
cd backend
python3.13 -m venv venv      # any Python 3.11+ works; avoid brand-new pre-release versions
venv/bin/pip install -r requirements.txt
cp .env.example .env         # optional — sane defaults work out of the box
venv/bin/python -m app.seed  # seeds departments, staff logins, POIs, and demo issues
venv/bin/uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
cp .env.example .env         # VITE_API_URL=http://localhost:8000
npm run dev
```

App: http://localhost:5173

## Demo Credentials (Municipal Staff)

| Username     | Password       | Role     | Department               |
|--------------|----------------|----------|---------------------------|
| `admin`      | `admin123`     | Admin    | —                          |
| `roads`      | `roads123`     | Officer  | Roads / Public Works       |
| `sanitation` | `sanitation123`| Officer  | Solid Waste Management     |
| `electrical` | `electrical123`| Officer  | Street Lighting / Electrical |
| `drainage`   | `drainage123`  | Officer  | Storm Water Drainage        |

Citizens don't need an account — just a name and mobile number (guest identity).

## Offline Demo

1. Open the citizen app once while online (so the PWA shell caches).
2. Turn off your network / DevTools → Network → Offline.
3. Report an issue (photo + GPS + description) and submit — you'll see **"Report saved offline"**, and it appears under **Pending Reports** with status *Waiting to sync*.
4. Refresh the page — the pending report is still there (IndexedDB persists).
5. Turn the network back on — within seconds the app detects connectivity, checks `/health`, and syncs automatically: status flips to *Syncing* → *Synced*, no manual resubmission needed.
6. The synced report goes through the full backend pipeline (spam check, AI classification, duplicate detection, priority, routing) exactly like an online submission, and appears on the municipal dashboard/map.

## API Overview

`GET /health` · `POST /auth/login` · `POST /citizen/reports` · `GET /citizen/reports/{complaint_id}` · `GET /citizen/my-reports` · `POST /issues/{complaint_id}/confirm-resolution` · `GET /staff/issues` · `GET /staff/issues/{id}` · `POST /staff/issues/{id}/accept|start-work|transfer|resolve|note|review-decision` · `GET /dashboard/summary` · `GET /dashboard/map` · `GET /analytics/departments|categories|hotspots` · `GET /notifications` · `GET /departments`

Full interactive schema at `/docs` (Swagger UI) once the backend is running.

## AI Fallback

`AI_PROVIDER=mock` (the default) uses a deterministic keyword-matching classifier against a 40+ issue-type taxonomy — no API key required, and the demo **never breaks** if an external AI provider is unavailable or unconfigured. Swapping in a real LLM provider later only means implementing `_classify_with_provider` in `backend/app/services/ai_classifier.py`; everything downstream (severity, routing, priority) is provider-agnostic.

## Future Enhancements

- Real LLM-backed image classification and translation.
- SMS/WhatsApp/push notification channels (the `notification_service` is already channel-agnostic).
- PostgreSQL + PostGIS for production-scale geospatial queries.
- Cloud object storage for uploaded images (storage is already abstracted behind `file_storage.py`).
- More Indian languages beyond English/Tamil.
