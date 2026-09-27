from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models_agent_access import AgentEntitlement, AgentUsage

FREE_DAILY_APPLICATIONS = 10
FREE_DAILY_DISCOVERIES = 250


def _today():
    return datetime.now(timezone.utc).date().isoformat()


def get_or_create_entitlement(db: Session, user_id: int) -> AgentEntitlement:
    entitlement = db.query(AgentEntitlement).filter(
        AgentEntitlement.user_id == user_id
    ).first()
    if entitlement:
        return entitlement

    entitlement = AgentEntitlement(
        user_id=user_id,
        tier="FREE",
        advanced_enabled=False,
        premium_crawling_enabled=False,
        cloud_browser_enabled=False,
        serp_discovery_enabled=False,
        daily_application_limit=FREE_DAILY_APPLICATIONS,
        daily_discovery_limit=FREE_DAILY_DISCOVERIES,
    )
    db.add(entitlement)
    db.flush()
    return entitlement


def get_usage(db: Session, user_id: int) -> AgentUsage:
    usage = db.query(AgentUsage).filter(
        AgentUsage.user_id == user_id,
        AgentUsage.usage_date == _today(),
    ).first()
    if usage:
        return usage

    usage = AgentUsage(user_id=user_id, usage_date=_today())
    db.add(usage)
    db.flush()
    return usage


def advanced_active(entitlement: AgentEntitlement) -> bool:
    if not entitlement.advanced_enabled or entitlement.tier.upper() != "ADVANCED":
        return False
    if entitlement.expires_at is not None:
        expires = entitlement.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            return False
    return True


def capabilities(entitlement: AgentEntitlement):
    advanced = advanced_active(entitlement)
    return {
        "tier": "ADVANCED" if advanced else "FREE",
        "advanced_enabled": advanced,
        "premium_crawling_enabled": bool(advanced and entitlement.premium_crawling_enabled),
        "cloud_browser_enabled": bool(advanced and entitlement.cloud_browser_enabled),
        "serp_discovery_enabled": bool(advanced and entitlement.serp_discovery_enabled),
    }
