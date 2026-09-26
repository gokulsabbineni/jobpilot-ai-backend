from fastapi import APIRouter,Depends,Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import active_user
from app.models import Job
r=APIRouter(prefix='/api/user/jobs',tags=['jobs'])
@r.get('')
def jobs(search:str|None=Query(None),db:Session=Depends(get_db),u=Depends(active_user)):
 q=db.query(Job)
 if search: q=q.filter((Job.title.ilike(f'%{search}%'))|(Job.company.ilike(f'%{search}%')))
 return q.all()
@r.get('/{job_id}')
def job(job_id:int,db:Session=Depends(get_db),u=Depends(active_user)): return db.get(Job,job_id)
