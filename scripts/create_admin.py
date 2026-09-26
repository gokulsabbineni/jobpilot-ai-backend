import os
import sys

from app.db import SessionLocal, init_db
from app.models import User
from app.security import hash_password


def main():
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")

    if not email or not password:
        print("Set ADMIN_EMAIL and ADMIN_PASSWORD before running this script.")
        sys.exit(1)

    if len(password) < 12:
        print("ADMIN_PASSWORD must be at least 12 characters.")
        sys.exit(1)

    init_db()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()

        if user:
            user.first_name = user.first_name or "JobPilot"
            user.last_name = user.last_name or "Admin"
            user.role = "ADMIN"
            user.status = "ACTIVE"
            user.password_hash = hash_password(password)
            db.commit()
            print(f"Admin credentials updated for {email}.")
            return

        user = User(
            first_name="JobPilot",
            last_name="Admin",
            email=email,
            password_hash=hash_password(password),
            role="ADMIN",
            status="ACTIVE",
        )
        db.add(user)
        db.commit()
        print(f"Admin account created for {email}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
