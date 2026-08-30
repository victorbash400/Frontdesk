# Deployment

The Cloud Run frontend (or localhost during development) calls the Cloud Run API.
The API owns the tool gateway,
browser relay, and PostgreSQL-backed application state. Agent Engine runs the
scoped ADK agent definitions and calls back through the authenticated tool gateway.

## Release checks

- Run the backend test suite with `requirements-dev.txt` installed.
- Run `python -m pip check` in both backend and Agent Engine build environments.
- Inspect `gcloud meta list-files-for-upload` before submitting a build. The root
  `.gcloudignore` allows only the Dockerfile's backend inputs. Local databases,
  screenshots, frontend assets, native builds, and environment files are excluded.
- Stage Agent Engine with `deploy_agent_engine.py`; its package is separate from
  the backend and contains only `agent_runtime` Python files and requirements.
- Keep the Agent Engine runtime requirements aligned with the environment that
  serializes it. ADK and Gen AI SDK class internals are part of the serialized
  artifact; an uncoordinated upgrade can make the remote agent fail before its
  first model request.
- Deploy a tagged Cloud Run revision with no traffic, verify authenticated API
  reads and a real Agent Engine tool round trip, then promote that exact revision.
- Check both Cloud Run and Agent Engine logs after promotion.

## Runtime identity

Use the configured runtime service account, not developer credentials. It needs
Vertex AI access, Cloud SQL access, and access to the configured secrets. Because
Agent Engine tracing is enabled, it also needs `roles/cloudtrace.agent` on the
project. Missing that role causes trace exports to fail with HTTP 403 even when
model calls work.

Scheduler requests use OIDC with the configured service account and exact
audience. The tool gateway validates each scoped run ticket. Browser relays use
database-backed identities and notifications so the extension and worker can
connect to different Cloud Run instances.

## Frontend release

Production: https://front-desk-web-222990066722.us-central1.run.app

The frontend is a Next.js standalone container, separate from the API and Agent
Engine. Its runtime service account needs access only to its authentication secret
and the shared API internal secret. Configure `AUTH_URL` with the public frontend
origin and `FRONT_DESK_BACKEND_URL` with the canonical API URL. Bind `AUTH_SECRET`
and `FRONT_DESK_INTERNAL_SECRET` through Secret Manager, never build arguments.
Include the frontend origin in the API's `FRONT_DESK_CORS_ORIGINS`; retain localhost
when local development is still needed. Provider OAuth callbacks stay on the API.

Stage frontend builds with `infra/stage_frontend.py` into a new temporary directory.
Submit that directory using `infra/cloudbuild.frontend.yaml` and substitutions
`_APP_ORIGIN`, `_API_ORIGIN`, and `_IMAGE`. The allowlist excludes credentials,
databases, screenshots, local records, native builds, and generated dependencies.
The runtime image contains only standalone server files, static assets, and public
files. Deploy the resulting immutable image digest, then run:

```sh
backend/.venv/bin/python infra/smoke_frontend.py https://front-desk-web-222990066722.us-central1.run.app
```

The smoke test reads existing demo-account data; it never creates goals, sends
messages, or modifies orders. It checks authentication, application reads, event
stream delivery, and the downloadable extension archive. Also inspect rendered
screens and Cloud Run errors before considering a release verified.

## Chrome extension distribution

`/extension` provides instructions and `/downloads/front-desk-extension.zip`.
The frontend build compiles the extension with the production app and API origins,
then packages only its output. Unzip it and load that directory using Chrome's
Load unpacked option. Keep Front Desk open in that same Chrome profile.

The archive does not contain the macOS Agent Mike/Agent Ears audio driver. Real
Google Meet voice still requires those installed devices. Archive and API tests
do not prove a real Chrome relay connection or a real two-way voice call; verify
those separately in the profile where the extension is installed.

## Database connection budget

Cloud Run is capped at two instances. Each instance retains at most two application
connections, one shared ADK session connection, and one event listener. Application
overflow is capped at five and ADK overflow at one; event publishing uses a short-lived
connection. Budget up to eleven connections per instance, plus release overlap and
diagnostic jobs. Cloud SQL uses `max_connections=50`. Recheck this budget before
increasing the Cloud Run instance cap; the original 25-connection database prevented
both workers and replacement revisions from starting.

Authentication releases its database session before streaming. Event subscribers
share a single LISTEN connection per event loop, with account-scoped delivery.
