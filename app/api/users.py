from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import active_user
from app.models import User,UserPreferences
from app.schemas import Preferences
r=APIRouter(prefix='/api/user',tags=['user'])
@r.get('/profile')
def profile(u=Depends(active_user)): return {'id':u.id,'first_name':u.first_name,'last_name':u.last_name,'email':u.email,'role':u.role,'status':u.status}
@r.get('/preferences',response_model=Preferences)
def prefs(db:Session=Depends(get_db),u=Depends(active_user)): return db.query(UserPreferences).filter_by(user_id=u.id).first()
@r.put('/preferences',response_model=Preferences)
def set_prefs(p:Preferences,db:Session=Depends(get_db),u=Depends(active_user)):
 x=db.query(UserPreferences).filter_by(user_id=u.id).first()
 for k,v in p.model_dump().items(): setattr(x,k,v)
 db.commit(); db.refresh(x); return x
@r.get('/dashboard')
def dashboard(db:Session=Depends(get_db),u=Depends(active_user)):
 return {'user':{'id':u.id,'name':f'{u.first_name} {u.last_name}','status':u.status},'resume':{'uploaded':bool(u.resume),'fileName':u.resume.file_name if u.resume else None},'jobs':{'matching':db.query(__import__('app.models',fromlist=['Job']).Job).count()},'applications':{'submitted':sum(a.status=='SUBMITTED' for a in u.applications),'total':len(u.applications)},'agent':{'status':u.agent_runs[-1].status if u.agent_runs else 'IDLE'},'action_required':sum(not a.completed for a in u.actions)}
