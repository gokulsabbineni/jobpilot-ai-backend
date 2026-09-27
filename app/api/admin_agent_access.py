from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import admin_user
from app.models import AuditLog, User
from app.services.agent_access import capabilities, get_or_create_entitlement, get_usage


r = APIRouter(prefix="/api/admin", tags=["admin-agent-access"])


def _serialize(entitlement):
    return {
        "user_id": entitlement.user_id,
        "tier": entitlement.tier,
        "advanced_enabled": entitlement.advanced_enabled,
        "premium_crawling_enabled": entitlement.premium_crawling_enabled,
        "cloud_browser_enabled": entitlement.cloud_browser_enabled,
        "serp_discovery_enabled": entitlement.serp_discovery_enabled,
        "daily_application_limit": entitlement.daily_application_limit,
        "daily_discovery_limit": entitlement.daily_discovery_limit,
        "expires_at": entitlement.expires_at,
        "effective": capabilities(entitlement),
    }


def _audit(db, admin, user_id, details):
    db.add(AuditLog(
        user_id=admin.id,
        action="UPDATE_AGENT_ENTITLEMENT",
        resource="agent_entitlement",
        resource_id=str(user_id),
        details=details,
    ))


@r.get("/agent-access")
def list_agent_access(db: Session = Depends(get_db), admin=Depends(admin_user)):
    users = db.query(User).filter(User.role != "ADMIN").order_by(User.id.desc()).all()
    result = []
    for user in users:
        entitlement = get_or_create_entitlement(db, user.id)
        result.append({
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "status": user.status,
            **_serialize(entitlement),
        })
    db.commit()
    return result


@r.get("/users/{user_id}/agent-access")
def get_user_agent_access(user_id: int, db: Session = Depends(get_db), admin=Depends(admin_user)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    entitlement = get_or_create_entitlement(db, user_id)
    db.commit()
    return {
        "user": {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "status": user.status,
        },
        **_serialize(entitlement),
    }


@r.put("/users/{user_id}/agent-access")
def update_user_agent_access(user_id: int, payload: dict, db: Session = Depends(get_db), admin=Depends(admin_user)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.role == "ADMIN":
        raise HTTPException(400, "Admin accounts do not need agent entitlements.")

    entitlement = get_or_create_entitlement(db, user_id)

    if "advanced_enabled" in payload:
        entitlement.advanced_enabled = bool(payload["advanced_enabled"])
    if "tier" in payload:
        tier = str(payload["tier"]).upper()
        if tier not in {"FREE", "ADVANCED"}:
            raise HTTPException(400, "tier must be FREE or ADVANCED")
        entitlement.tier = tier
    if "premium_crawling_enabled" in payload:
        entitlement.premium_crawling_enabled = bool(payload["premium_crawling_enabled"])
    if "cloud_browser_enabled" in payload:
        entitlement.cloud_browser_enabled = bool(payload["cloud_browser_enabled"])
    if "serp_discovery_enabled" in payload:
        entitlement.serp_discovery_enabled = bool(payload["serp_discovery_enabled"])
    if "daily_application_limit" in payload:
        entitlement.daily_application_limit = max(0, int(payload["daily_application_limit"]))
    if "daily_discovery_limit" in payload:
        entitlement.daily_discovery_limit = max(0, int(payload["daily_discovery_limit"]))
    if "expires_at" in payload:
        entitlement.expires_at = payload["expires_at"]

    entitlement.tier = "ADVANCED" if entitlement.advanced_enabled else "FREE"

    _audit(db, admin, user_id, {
        "tier": entitlement.tier,
        "advanced_enabled": entitlement.advanced_enabled,
        "premium_crawling_enabled": entitlement.premium_crawling_enabled,
        "cloud_browser_enabled": entitlement.cloud_browser_enabled,
        "serp_discovery_enabled": entitlement.serp_discovery_enabled,
        "daily_application_limit": entitlement.daily_application_limit,
        "daily_discovery_limit": entitlement.daily_discovery_limit,
        "expires_at": entitlement.expires_at.isoformat() if entitlement.expires_at else None,
    })
    db.commit()
    db.refresh(entitlement)
    return _serialize(entitlement)


@r.get("/agent-usage")
def agent_usage(db: Session = Depends(get_db), admin=Depends(admin_user)):
    users = db.query(User).filter(User.role != "ADMIN").all()
    result = []
    for user in users:
        entitlement = get_or_create_entitlement(db, user.id)
        usage = get_usage(db, user.id)
        result.append({
            "user_id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "tier": capabilities(entitlement)["tier"],
            "usage": {
                "date": usage.usage_date,
                "discovery_requests": usage.discovery_requests,
                "jobs_discovered": usage.jobs_discovered,
                "pages_crawled": usage.pages_crawled,
                "browser_minutes": usage.browser_minutes,
                "applications_attempted": usage.applications_attempted,
                "applications_submitted": usage.applications_submitted,
                "llm_requests": usage.llm_requests,
            },
        })
    db.commit()
    return result
