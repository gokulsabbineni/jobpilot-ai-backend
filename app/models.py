from datetime import datetime, timezone
from sqlalchemy import Column,Integer,String,Text,Boolean,DateTime,ForeignKey,Float,JSON
from sqlalchemy.orm import relationship
from app.db import Base

def now():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__='users'
    id=Column(Integer,primary_key=True)
    first_name=Column(String(100),nullable=False)
    last_name=Column(String(100),nullable=False)
    email=Column(String(255),unique=True,index=True,nullable=False)
    password_hash=Column(String(255),nullable=False)
    role=Column(String(20),default='USER',nullable=False)
    status=Column(String(40),default='PENDING_APPROVAL',nullable=False)
    created_at=Column(DateTime(timezone=True),default=now)
    updated_at=Column(DateTime(timezone=True),default=now,onupdate=now)
    last_login_at=Column(DateTime(timezone=True))
    resume=relationship('Resume',back_populates='user',uselist=False,cascade='all, delete-orphan')
    preferences=relationship('UserPreferences',back_populates='user',uselist=False,cascade='all, delete-orphan')
    applications=relationship('Application',back_populates='user',cascade='all, delete-orphan')
    agent_runs=relationship('AgentRun',back_populates='user',cascade='all, delete-orphan')
    actions=relationship('ActionRequired',back_populates='user',cascade='all, delete-orphan')

class Resume(Base):
    __tablename__='resumes'
    id=Column(Integer,primary_key=True)
    user_id=Column(Integer,ForeignKey('users.id'),unique=True,nullable=False)
    file_name=Column(String(255),nullable=False)
    file_path=Column(String(500))
    content_text=Column(Text)
    parsed_profile=Column(JSON,default=dict)
    uploaded_at=Column(DateTime(timezone=True),default=now)
    user=relationship('User',back_populates='resume')

class UserPreferences(Base):
    __tablename__='user_preferences'
    id=Column(Integer,primary_key=True)
    user_id=Column(Integer,ForeignKey('users.id'),unique=True,nullable=False)
    job_types=Column(JSON,default=list)
    job_titles=Column(JSON,default=list)
    locations=Column(JSON,default=list)
    remote_preference=Column(String(30),default='ANY')
    salary_min=Column(Integer)
    salary_max=Column(Integer)
    sponsorship_required=Column(Boolean,default=False)
    auto_apply=Column(Boolean,default=False)
    user=relationship('User',back_populates='preferences')

class Job(Base):
    __tablename__='jobs'
    id=Column(Integer,primary_key=True)
    company=Column(String(255),nullable=False)
    title=Column(String(255),nullable=False)
    description=Column(Text)
    location=Column(String(255))
    job_type=Column(String(50))
    remote=Column(Boolean,default=False)
    salary_min=Column(Integer)
    salary_max=Column(Integer)
    url=Column(String(1000),nullable=False,index=True)
    source=Column(String(100))
    posted_at=Column(DateTime(timezone=True))
    created_at=Column(DateTime(timezone=True),default=now)

class Application(Base):
    __tablename__='applications'
    id=Column(Integer,primary_key=True)
    user_id=Column(Integer,ForeignKey('users.id'),nullable=False)
    job_id=Column(Integer,ForeignKey('jobs.id'),nullable=False)
    status=Column(String(50),default='DISCOVERED',nullable=False,index=True)
    match_score=Column(Float)
    external_url=Column(String(1000))
    provider=Column(String(50))
    attempt_count=Column(Integer,default=0,nullable=False)
    max_attempts=Column(Integer,default=3,nullable=False)
    last_error=Column(Text)
    next_retry_at=Column(DateTime(timezone=True))
    started_at=Column(DateTime(timezone=True))
    submitted_at=Column(DateTime(timezone=True))
    application_data=Column(JSON,default=dict)
    created_at=Column(DateTime(timezone=True),default=now)
    updated_at=Column(DateTime(timezone=True),default=now,onupdate=now)
    user=relationship('User',back_populates='applications')
    job=relationship('Job')
    actions=relationship('ActionRequired',back_populates='application',cascade='all, delete-orphan')

class AgentRun(Base):
    __tablename__='agent_runs'
    id=Column(Integer,primary_key=True)
    user_id=Column(Integer,ForeignKey('users.id'),nullable=False)
    status=Column(String(30),default='IDLE')
    jobs_scanned=Column(Integer,default=0)
    applications_made=Column(Integer,default=0)
    applications_submitted=Column(Integer,default=0)
    applications_action_required=Column(Integer,default=0)
    applications_failed=Column(Integer,default=0)
    started_at=Column(DateTime(timezone=True))
    completed_at=Column(DateTime(timezone=True))
    error_message=Column(Text)
    user=relationship('User',back_populates='agent_runs')

class ActionRequired(Base):
    __tablename__='action_required'
    id=Column(Integer,primary_key=True)
    user_id=Column(Integer,ForeignKey('users.id'),nullable=False)
    application_id=Column(Integer,ForeignKey('applications.id'))
    type=Column(String(50))
    title=Column(String(255))
    description=Column(Text)
    required=Column(Boolean,default=True)
    completed=Column(Boolean,default=False)
    response=Column(JSON)
    created_at=Column(DateTime(timezone=True),default=now)
    completed_at=Column(DateTime(timezone=True))
    user=relationship('User',back_populates='actions')
    application=relationship('Application',back_populates='actions',foreign_keys=[application_id])

class AuditLog(Base):
    __tablename__='audit_logs'
    id=Column(Integer,primary_key=True)
    user_id=Column(Integer,ForeignKey('users.id'))
    action=Column(String(100))
    resource=Column(String(100))
    resource_id=Column(String(100))
    details=Column(JSON,default=dict)
    created_at=Column(DateTime(timezone=True),default=now)

class SystemSetting(Base):
    __tablename__='system_settings'
    id=Column(Integer,primary_key=True)
    key=Column(String(100),unique=True)
    value=Column(JSON)
    updated_at=Column(DateTime(timezone=True),default=now,onupdate=now)


class JobDiscovery(Base):
    __tablename__='job_discoveries'
    id=Column(Integer,primary_key=True)
    job_id=Column(Integer,ForeignKey('jobs.id'),nullable=False,index=True)
    canonical_url=Column(String(1200),nullable=False,index=True)
    fingerprint=Column(String(128),unique=True,index=True,nullable=False)
    external_id=Column(String(255),index=True)
    provider=Column(String(80),nullable=False,index=True)
    source_url=Column(String(1200))
    first_seen_at=Column(DateTime(timezone=True),default=now,index=True)
    last_seen_at=Column(DateTime(timezone=True),default=now,index=True)
    last_checked_at=Column(DateTime(timezone=True))
    active=Column(Boolean,default=True,index=True)
    discovery_count=Column(Integer,default=1,nullable=False)
    raw_data=Column(JSON,default=dict)
    crawl_error=Column(Text)
    job=relationship('Job',backref='discovery')
