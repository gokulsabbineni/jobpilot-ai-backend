import os

from app.db import SessionLocal, init_db
from app.models import ActionRequired, Job, User, UserPreferences
from app.security import hash_password


init_db()
db = SessionLocal()


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} must be set before running seed.py")
    return value


def user(email, first, last, password, role, status):
    existing = db.query(User).filter_by(email=email).first()
    if existing:
        return existing

    created = User(
        email=email,
        first_name=first,
        last_name=last,
        password_hash=hash_password(password),
        role=role,
        status=status,
    )
    db.add(created)
    db.flush()
    db.add(
        UserPreferences(
            user_id=created.id,
            job_types=["FULL_TIME", "CONTRACT"],
            job_titles=["Golang Backend Engineer", "Software Engineer"],
            locations=["Dallas", "Remote"],
            remote_preference="ANY",
        )
    )
    return created


admin = user(
    required_env("ADMIN_EMAIL"),
    "JobPilot",
    "Admin",
    required_env("ADMIN_PASSWORD"),
    "ADMIN",
    "ACTIVE",
)

normal = user(
    os.getenv("DEMO_USER_EMAIL", "demo.user@example.com"),
    "Demo",
    "User",
    os.getenv("DEMO_USER_PASSWORD", required_env("ADMIN_PASSWORD")),
    "USER",
    "ACTIVE",
)

pending = user(
    os.getenv("PENDING_USER_EMAIL", "pending.user@example.com"),
    "Pending",
    "User",
    os.getenv("PENDING_USER_PASSWORD", required_env("ADMIN_PASSWORD")),
    "USER",
    "PENDING_APPROVAL",
)

if db.query(Job).count() == 0:
    db.add_all(
        [
            Job(
                company="Example Technologies",
                title="Golang Backend Engineer",
                description="Go APIs PostgreSQL Redis",
                location="Dallas, TX",
                job_type="FULL_TIME",
                remote=True,
                url="https://example.com/jobs/1",
                source="DEMO",
            ),
            Job(
                company="Cloud Systems Inc.",
                title="Software Engineer",
                description="Cloud backend services",
                location="Remote",
                job_type="CONTRACT",
                remote=True,
                url="https://example.com/jobs/2",
                source="DEMO",
            ),
            Job(
                company="Data Platform Co.",
                title="Backend Developer",
                description="Python FastAPI PostgreSQL",
                location="Austin, TX",
                job_type="FULL_TIME",
                remote=False,
                url="https://example.com/jobs/3",
                source="DEMO",
            ),
        ]
    )

if not db.query(ActionRequired).filter_by(user_id=normal.id).first():
    db.add(
        ActionRequired(
            user_id=normal.id,
            type="PROFILE",
            title="Confirm work authorization",
            description="Provide information required before an application can be submitted.",
        )
    )

db.commit()
print("Seed complete")
