from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import active_user
from app.models import AgentRun,Job,Application
r=APIRouter(prefix='/api/user/agent',tags=['agent'])
def out(x): return {'id':x.id if x else None,'status':x.status if x else 'IDLE','jobs_scanned':x.jobs_scanned if x else 0,'applications_made':x.applications_made if x else 0}
@r.get('')
def status(db:Session=Depends(get_db),u=Depends(active_user)): return out(db.query(AgentRun).filter_by(user_id=u.id).order_by(AgentRun.id.desc()).first())
@r.post('/start')
def start(db:Session=Depends(get_db),u=Depends(active_user)):
 if not u.resume: raise HTTPException(400,'Upload a resume before starting the agent')
 x=AgentRun(user_id=u.id,status='RUNNING',started_at=datetime.now(timezone.utc)); db.add(x); db.flush(); jobs=db.query(Job).limit(20).all(); x.jobs_scanned=len(jobs)
 for j in jobs:
  if not db.query(Application).filter_by(user_id=u.id,job_id=j.id).first(): db.add(Application(user_id=u.id,job_id=j.id,status='READY',match_score=70,external_url=j.url)); x.applications_made+=1
 x.status='COMPLETED'; x.completed_at=datetime.now(timezone.utc); db.commit(); return out(x)
@r.post('/pause')
def pause(db:Session=Depends(get_db),u=Depends(active_user)): return _change(db,u,'PAUSED')
@r.post('/stop')
def stop(db:Session=Depends(get_db),u=Depends(active_user)): return _change(db,u,'STOPPED')
def _change(db,u,status):
 x=db.query(AgentRun).filter_by(user_id=u.id).order_by(AgentRun.id.desc()).first()
 if not x: raise HTTPException(404,'No agent run found')
 x.status=status; db.commit(); return out(x)
