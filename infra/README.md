# Backend deployment

The local frontend calls Cloud Run. Cloud Run owns the API, tool gateway,
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

Keep the frontend on localhost until the separate frontend deployment is ready.
Extension distribution packaging is a separate release step.

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
