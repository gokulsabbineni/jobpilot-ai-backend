# JobPilot AI Backend

FastAPI backend with JWT auth, admin approval, resume upload, jobs, applications, action-required workflow, agent lifecycle, Ollama/OpenAI provider abstraction, SQLite local development and PostgreSQL-ready configuration.

## Run

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python seed.py
uvicorn app.main:app --reload --port 8000

Docs: http://localhost:8000/docs

Admin: admin@jobpilot.ai / Admin123!
User: alex.johnson@example.com / User123!
Pending: pending.user@example.com / User123!

For production, use PostgreSQL, Redis, private object storage, background workers, HTTPS, secrets management, rate limiting, migrations, monitoring and permitted job-source adapters. Do not bypass CAPTCHA/MFA/access controls.
