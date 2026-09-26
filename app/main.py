from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db
from app.services.admin_bootstrap import ensure_admin
from app.api.auth import r as auth
from app.api.users import r as users
from app.api.resumes import r as resumes
from app.api.jobs import r as jobs
from app.api.applications import r as applications
from app.api.action_required import r as actions
from app.api.agent import r as agent
from app.api.admin import r as admin
from app.api.application_runner import r as application_runner


@asynccontextmanager
async def lifespan(app):
    init_db()
    ensure_admin()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for x in [
    auth,
    users,
    resumes,
    jobs,
    application_runner,
    actions,
    agent,
    admin,
]:
    app.include_router(x)


@app.get("/")
def root():
    return {"name": settings.app_name, "status": "ok"}


@app.get("/health")
def health():
    return {"status": "healthy"}
