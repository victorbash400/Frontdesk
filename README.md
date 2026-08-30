# Front Desk

Front Desk is a client-work workspace with direct Gemini chat, visible model reasoning summaries, Markdown responses, tasks, goals, skills, and plugin connections. Its interface follows the Operator product language while the agent runtime uses Google Agent Development Kit and Vertex AI.

## Stack

- Next.js 16, React 19, Auth.js, and CSS Modules
- FastAPI, SQLAlchemy, and SQLite/PostgreSQL-compatible account storage
- Persistent account/chat-scoped ADK sessions through `DatabaseSessionService`
- Persisted client goals, assignments, clarification inboxes, and scheduled wakes in SQLite or PostgreSQL
- Google ADK with `gemini-3-flash-preview` on Vertex AI
- Separate Gemini Live voice sessions using `gemini-3.1-flash-live-preview`
- Server-sent events for chat and goal updates; no polling
- Google Cloud Storage for future client artifacts
- Account-scoped Gmail, Drive, and Google Docs tools through Google Workspace OAuth

## Local setup

1. Copy `.env.example` to `.env.local` and `backend/.env.example` to `backend/.env`.
2. Run `pnpm install`.
3. Create `backend/.venv` and install `backend/requirements-dev.txt` for local development and tests. Production uses `backend/requirements.txt`.
4. Authenticate Application Default Credentials and set `front-desk-20260824` as the quota project.
5. Run `pnpm backend` and `pnpm dev` in separate terminals when you are ready to run the app.

The demo account is `demo@front-desk.local` with password `front-desk-demo`.

The current goal worker runs locally inside the FastAPI process and is structured for a later Cloud Run deployment. A production deployment still needs an external durable dispatch service before goal execution can survive instance termination or scale-to-zero.
