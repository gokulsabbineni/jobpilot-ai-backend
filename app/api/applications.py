from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import active_user
from app.models import Application,Job
r=APIRouter(prefix='/api/user/applications',tags=['applications'])
@r.get('')
def apps(db:Session=Depends(get_db),u=Depends(active_user)): return db.query(Application).filter_by(user_id=u.id).all()
@r.post('/jobs/{job_id}')
def apply(job_id:int,db:Session=Depends(get_db),u=Depends(active_user)):
 j=db.get(Job,job_id)
 if not j: raise HTTPException(404,'Job not found')
 x=Application(user_id=u.id,job_id=j.id,status='READY',match_score=0,external_url=j.url); db.add(x); db.commit(); db.refresh(x); return x
