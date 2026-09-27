from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.db import Base


def now():
    return datetime.now(timezone.utc)


class AgentEntitlement(Base):
    __tablename__ = "agent_entitlements"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    tier = Column(String(30), nullable=False, default="FREE")
    advanced_enabled = Column(Boolean, nullable=False, default=False)
    premium_crawling_enabled = Column(Boolean, nullable=False, default=False)
    cloud_browser_enabled = Column(Boolean, nullable=False, default=False)
    serp_discovery_enabled = Column(Boolean, nullable=False, default=False)
    daily_application_limit = Column(Integer, nullable=False, default=10)
    daily_discovery_limit = Column(Integer, nullable=False, default=250)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=now)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)


class AgentUsage(Base):
    __tablename__ = "agent_usage"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    usage_date = Column(String(10), nullable=False, index=True)
    discovery_requests = Column(Integer, nullable=False, default=0)
    jobs_discovered = Column(Integer, nullable=False, default=0)
    pages_crawled = Column(Integer, nullable=False, default=0)
    browser_minutes = Column(Integer, nullable=False, default=0)
    applications_attempted = Column(Integer, nullable=False, default=0)
    applications_submitted = Column(Integer, nullable=False, default=0)
    llm_requests = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=now)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (
        UniqueConstraint("user_id", "usage_date", name="uq_agent_usage_user_date"),
    )
