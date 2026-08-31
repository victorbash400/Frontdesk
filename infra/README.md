# Deployment

The Cloud Run frontend (or localhost during development) calls the Cloud Run API.
The API owns the tool gateway,
browser relay, and PostgreSQL-backed application state. Agent Engine runs the
scoped ADK agent definitions and calls back through the authenticated tool gateway.

## Release checks

- Run the backend test suite with `requirements-dev.txt` installed.
- Keep the container interpreter at the Python version the tests run on. The mailbox
  listener calls `imaplib.IMAP4.idle()`, which exists only from Python 3.14; on an
  older base image the IDLE wait fails every cycle with `Unknown IMAP4 command: 'idle'`
  and live mail delivery silently degrades to retry polling.
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

Cloud SQL uses `max_connections=50` on a `db-f1-micro` instance; Cloud Run is capped at
two instances. Per instance the ceiling is fourteen connections:

- Ten application connections: `pool_size=5` with `max_overflow=5`.
- One runtime ownership lease, outside the query pool.
- Two ADK session connections: `pool_size=1` with `max_overflow=1`.
- One event listener; event publishing uses a short-lived connection.

Steady state is two instances at twenty-eight connections. A release adds a tagged
revision that takes no traffic until promotion, so realistic overlap is three instances
at forty-two. Four instances all at full overflow would exceed the server, which is why
the tagged revision must stay at no traffic and why the instance cap cannot rise without
also raising `max_connections` or the instance tier. The original 25-connection database
prevented both workers and replacement revisions from starting.

Runtime ownership is the reason the pools are split. Advisory locks are session scoped,
so a lease holds its connection for the entire life of the work it guards: a mailbox
listener holds one indefinitely, and a single inbound email holds several more across
its message lock, its agent session lock, and the goal it dispatches. Sharing one pool
between those leases and ordinary queries exhausted it and timed the Email Agent out
after thirty seconds. All leases now share one connection on a separate `NullPool`
engine, since distinct advisory keys can be held together on one session. That makes
lease cost constant per instance instead of growing with concurrent work, and it means
in-process ownership is decided in memory before PostgreSQL arbitrates between
instances. If the lease connection drops, its locks release server side; the reconnect
is logged, and ownership within the process is unaffected.

Authentication releases its database session before streaming. Event subscribers
share a single LISTEN connection per event loop, with account-scoped delivery.
