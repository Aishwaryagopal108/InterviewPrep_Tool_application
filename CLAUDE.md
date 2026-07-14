# Interview Prep App

## What this is
A web app that: uploads a resume PDF, extracts projects/initiatives and the concepts to study from it via an LLM, generates study content per concept, generates a STAR-style story per project (objective, data, methodology, results, challenges, future scope), generates likely interview Q&A per project, and generates resume-wide technical Q&A.

## Stack (all free tier)
- Frontend: plain HTML/CSS/JS, no framework
- Backend: Python + FastAPI
- LLM: Groq API (open source models, e.g. openai/gpt-oss-120b), free tier, no card required
- Database: Postgres via Supabase, free tier — **deferred to Phase 2, not used yet** (see Phasing below)
- Hosting: Render (free tier) — one static site for the frontend, one web service for the backend
- Version control: GitHub (Render deploys from here)
- Editor: VS Code

## Phasing
This project is being built in two phases:

- **Phase 1 (current): stateless prototype.** One resume per browser visit. Upload -> extract -> dashboard -> on-demand generation (study/story/Q&A) all happen live against Groq, with results held only in browser memory for that session. Nothing is persisted — refreshing the page loses everything. This validates the full user-facing flow (extraction quality, dashboard rendering, all four generation prompts) before investing in a database.
- **Phase 2 (deferred): persistence.** Postgres via Supabase, multi-resume support, anonymous per-browser identification via `anon_id`, caching every generated result so it's never regenerated. The schema is already designed (see "Phase 2: persistence design" below) so switching over is mechanical once Phase 1 is proven out.

## Architecture (Phase 1)
Browser -> Render static site (frontend) -> Render web service (FastAPI backend) -> Groq API (generates content live, nothing cached)

Only the backend ever holds the Groq API key. Never expose it in frontend code or commit it to git — it lives in a backend `.env` file that's gitignored.

## Data flow (Phase 1 — stateless prototype)
1. User uploads a resume PDF -> `POST /upload` extracts raw text (pdfplumber) -> returned to the browser and held in memory for that session (not persisted)
2. Browser immediately sends that text to `POST /extract` -> Groq returns structured JSON: a list of initiatives, each with title, company, timeframe, description, concepts, tags
3. The frontend renders the initiative dashboard (card grid) directly from that response — no database involved
4. On demand, per card/concept, the browser calls a generation endpoint and renders the result live. Nothing is cached, so re-triggering the same generation calls Groq again:
   - `POST /study` — a multi-dimension deep dive per concept
   - `POST /story` — objective / data / methodology / results / challenges / future scope per initiative
   - `POST /project-qa` — likely interview questions + strong answers per initiative
   - `POST /resume-qa` — resume-wide technical Q&A, using the full resume text already held in browser memory

## Build order (Phase 1)
1. Throwaway script: resume text in -> Groq call -> structured JSON out. (done)
2. FastAPI `/upload` endpoint (PDF -> text) (done)
3. FastAPI `/extract` endpoint (done)
4. Frontend: upload page that calls `/upload` then `/extract` and renders the initiative dashboard from the response, held in browser memory
5. On-demand generation endpoints: `/study`, `/story`, `/project-qa`, `/resume-qa` — each calls Groq live and returns the result directly, no DB write
6. Test the full stateless prototype locally (done)
7. Push to GitHub, deploy the Phase 1 prototype to Render — backend as a web service, frontend as a static site, `GROQ_API_KEY` set as a Render environment variable (never committed), backend CORS locked to the deployed frontend origin (done — no Supabase involved, live at the two Render URLs)
8. **(Phase 2, later)** Postgres schema in Supabase, wire extraction + generation output into the database, multi-resume support + `anon_id`, connect Supabase to the deployed backend

## Phase 2: persistence design (deferred, not built yet)
No login/auth, no users table. Each browser will be anonymously identified by an `anon_id` (a UUID generated client-side and sent with every request) — this is how multiple people can use the same deployment without accounts, and how one browser's resumes stay separate from another's. **None of this exists in Phase 1** — the prototype has no concept of identity, sessions, or saved resumes at all.

- **resumes**: `id`, `anon_id` (the owning browser's UUID, not a FK — no users table exists), `label` (e.g. "Data Analyst — Total Wine", user-provided at upload), `uploaded_at`, `raw_text` (full extracted PDF text, reused for resume-wide Q&A)
- **initiatives**: `id`, `resume_id` (FK -> resumes.id), `title`, `company`, `timeframe` (nullable), `description`, `tags`
- **concepts**: `id`, `initiative_id` (FK -> initiatives.id), `name`, cached study content
- **stories**: `id`, `initiative_id` (FK -> initiatives.id), the STAR fields, cached
- **qa_pairs**: `id`, `initiative_id` (FK, nullable), `resume_id` (FK, nullable), `question`, `answer` — project Q&A rows set `initiative_id`; resume-wide Q&A rows set `resume_id` instead, since they aren't tied to one initiative

`concepts` and `stories` don't need their own `resume_id`/`anon_id` — they reach a resume transitively through `initiative_id -> initiatives.resume_id`. The dashboard's per-resume filtering will be `SELECT * FROM initiatives WHERE resume_id = :selected_resume_id`, but every such query is only reachable after the backend has already confirmed that resume's `anon_id` matches the caller's.

**Ownership enforcement (once built) will be entirely in application code, not Supabase RLS.** Every backend query that touches `resumes` (or anything linked to it via `resume_id`/`initiative_id`) must filter by the caller's `anon_id`. There's no database-level enforcement — a missing filter in a route handler is a real data leak between browsers, not just a style issue.

On first visit in Phase 2, the frontend will generate a random `anon_id` via `crypto.randomUUID()` and store it in `localStorage`, sending it with every request.

## Design decisions
- `timeframe` on an initiative is optional (nullable). Resumes commonly omit dates for personal projects while jobs have them. The frontend hides the timeframe line on a card when it's empty rather than showing a placeholder.
- Multi-user support (Phase 2) will be anonymous per-browser identification via `anon_id` — not accounts, not login. This replaces the earlier "Phase 2 multi-user" auth plan entirely; there is no plan to add real login/accounts on top of this later.
- Building stateless first (Phase 1) before persistence (Phase 2): validates the full user-facing flow — upload, extraction quality, dashboard rendering, and all four generation prompts — before investing in schema design, migrations, and caching logic. Phase 2's design is already settled (above) so the switch-over is mechanical.

## Rules to hold to
- API keys only ever live in the backend's `.env`, never in frontend code, never committed to git
- Phase 1 (current) intentionally caches nothing — every generation call hits Groq live. This is expected, not a bug; it also means Phase 1 testing is more likely to hit Groq's free-tier per-minute/per-day rate limits than Phase 2 will be, since there's no caching yet to absorb repeat requests
- Once Phase 2 lands: cache every LLM-generated result in Postgres, and every query touching `resumes`-linked data must filter by the caller's `anon_id` (enforced in application code, not Supabase RLS)
- Render's free web service spins down after 15 idle minutes (30-60s cold start on next request); Supabase free Postgres has no expiry but limited storage — relevant once deployed / once Phase 2 lands
