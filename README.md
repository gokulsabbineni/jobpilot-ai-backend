# JobPilot AI Backend

FastAPI backend for authentication, user preferences, resumes, job discovery, application preparation, action-required workflows, admin approval, and agent orchestration.

## Local development

Requirements: Python 3.12+.

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env
    ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD='use-a-strong-password' python seed.py
    uvicorn app.main:app --reload --port 8000

Health check: http://localhost:8000/health
API docs: http://localhost:8000/docs

## Tests

    pytest -q

GitHub Actions runs the backend test suite on pushes and pull requests.

## Production environment

Use PostgreSQL for DATABASE_URL, a strong generated SECRET_KEY, ENVIRONMENT=production, DEBUG=false, an explicit CORS_ORIGINS value containing the production frontend URL, and an LLM provider/API key if AI features are enabled.

Resume files are currently stored on the local filesystem. In a production deployment, attach persistent storage or replace the storage implementation with object storage before relying on uploaded resumes across deployments.

## Current agent scope

The current agent prepares matching application records from jobs already stored in the database. It does not yet submit forms to external employer portals. External portal automation should be added as a separate worker/browser subsystem with explicit user-controlled credentials, Action Required pauses for missing information/CAPTCHA, and strong audit logging.

## Docker

The Dockerfile supports a platform-provided PORT and can run locally with docker compose.
