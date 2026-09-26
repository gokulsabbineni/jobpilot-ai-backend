from app.config import settings
from app.db import SessionLocal
from app.models import User
from app.security import hash_password


def ensure_admin() -> None:
    email = (settings.admin_email or "").strip().lower()
    password = settings.admin_password or ""

    if not email and not password:
        print("Admin bootstrap skipped: ADMIN_EMAIL and ADMIN_PASSWORD are not configured.")
        return

    if not email or not password:
        raise RuntimeError(
            "ADMIN_EMAIL and ADMIN_PASSWORD must both be configured for admin bootstrap."
        )

    if len(password) < 12:
        raise RuntimeError("ADMIN_PASSWORD must be at least 12 characters.")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()

        if user:
            if user.role != "ADMIN":
                raise RuntimeError(
                    f"Admin bootstrap refused: {email} already belongs to a non-admin user."
                )

            if user.status != "ACTIVE":
                user.status = "ACTIVE"
                db.commit()

            print(f"Admin account verified for {email}.")
            return

        admin = User(
            first_name="JobPilot",
            last_name="Admin",
            email=email,
            password_hash=hash_password(password),
            role="ADMIN",
            status="ACTIVE",
        )
        db.add(admin)
        db.commit()

        print(f"Admin account created for {email}.")
    finally:
        db.close()
