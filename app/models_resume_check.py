from datetime import datetime, timezone
from sqlalchemy import Column, Integer, ForeignKey, DateTime, JSON, Float
from app.db import Base

def now():
    return datetime.now(timezone.utc)

class ResumeCheck(Base):
    __tablename__ = "resume_checks"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False)
    overall_score = Column(Float)
    ats_score = Column(Float)
    content_score = Column(Float)
    impact_score = Column(Float)
    readability_score = Column(Float)
    job_alignment_score = Column(Float)
    analysis = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=now)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)
