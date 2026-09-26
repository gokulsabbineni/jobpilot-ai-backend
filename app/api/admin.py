from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import admin_user
from app.models import User,AuditLog
r=APIRouter(prefix='/api/admin',tags=['admin'])
def audit(db,u,action,uid): db.add(AuditLog(user_id=u.id,action=action,resource='user',resource_id=str(uid)))
@r.get('/dashboard')
def dashboard(db:Session=Depends(get_db),u=Depends(admin_user)):
 return {'users':{'total':db.query(User).count(),'active':db.query(User).filter_by(status='ACTIVE').count(),'pending':db.query(User).filter_by(status='PENDING_APPROVAL').count()}}
@r.get('/users')
def users(db:Session=Depends(get_db),u=Depends(admin_user)): return db.query(User).order_by(User.id.desc()).all()
@r.get('/approvals')
def approvals(db:Session=Depends(get_db),u=Depends(admin_user)): return db.query(User).filter_by(status='PENDING_APPROVAL').all()
@r.post('/approvals/{uid}/approve')
def approve(uid:int,db:Session=Depends(get_db),u=Depends(admin_user)):
 x=db.get(User,uid)
 if not x: raise HTTPException(404,'User not found')
 x.status='ACTIVE'; audit(db,u,'APPROVE_USER',uid); db.commit(); return x
@r.post('/approvals/{uid}/reject')
def reject(uid:int,db:Session=Depends(get_db),u=Depends(admin_user)):
 x=db.get(User,uid)
 if not x: raise HTTPException(404,'User not found')
 x.status='REJECTED'; audit(db,u,'REJECT_USER',uid); db.commit(); return x
@r.get('/applications')
def applications(db:Session=Depends(get_db),u=Depends(admin_user)):
 from app.models import Application
 return db.query(Application).order_by(Application.id.desc()).all()
@r.get('/agent-activity')
def activity(db:Session=Depends(get_db),u=Depends(admin_user)):
 from app.models import AgentRun
 return db.query(AgentRun).order_by(AgentRun.id.desc()).all()
@r.get('/audit-logs')
def logs(db:Session=Depends(get_db),u=Depends(admin_user)): return db.query(AuditLog).order_by(AuditLog.id.desc()).limit(500).all()
