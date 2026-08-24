# Front Desk

Front Desk is a client-work workspace with direct Gemini chat, visible model reasoning summaries, Markdown responses, tasks, goals, skills, and plugin connections. Its interface follows the Operator product language while the agent runtime uses Google Agent Development Kit and Vertex AI.

## Stack

- Next.js 16, React 19, Auth.js, and CSS Modules
- FastAPI, SQLAlchemy, and SQLite/PostgreSQL-compatible account storage
- Persistent account/chat-scoped ADK sessions through `DatabaseSessionService`
- Google ADK with `gemini-3.6-flash` on Vertex AI
- Server-sent events for chat streaming; no polling
- Google Cloud Storage for future client artifacts
- Account-scoped Google Workspace OAuth foundation

## Local setup

1. Copy `.env.example` to `.env.local` and `backend/.env.example` to `backend/.env`.
2. Run `pnpm install`.
3. Create `backend/.venv` and install `backend/requirements.txt`.
4. Authenticate Application Default Credentials and set `front-desk-20260824` as the quota project.
5. Run `pnpm backend` and `pnpm dev` in separate terminals when you are ready to run the app.

The demo account is `demo@front-desk.local` with password `front-desk-demo`.

Workspace tools and voice are intentionally not included in this phase. Gmail, Drive, and Calendar share the Google Workspace connection that those tools will use next.
