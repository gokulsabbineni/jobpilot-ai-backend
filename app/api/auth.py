from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User,UserPreferences
from app.schemas import Register,Login,Token,UserOut
from app.security import hash_password,verify_password,create_access_token
from app.deps import current_user
r=APIRouter(prefix='/api/auth',tags=['auth'])
@r.post('/register',response_model=UserOut,status_code=201)
def register(p:Register,db:Session=Depends(get_db)):
 if db.query(User).filter(User.email==p.email.lower()).first(): raise HTTPException(409,'Email is already registered')
 u=User(first_name=p.first_name,last_name=p.last_name,email=p.email.lower(),password_hash=hash_password(p.password),role='USER',status='PENDING_APPROVAL'); db.add(u); db.flush(); db.add(UserPreferences(user_id=u.id)); db.commit(); db.refresh(u); return u
@r.post('/login',response_model=Token)
def login(p:Login,db:Session=Depends(get_db)):
 u=db.query(User).filter(User.email==p.email.lower()).first()
 if not u or not verify_password(p.password,u.password_hash): raise HTTPException(401,'Invalid email or password')
 if u.status!='ACTIVE': raise HTTPException(403,f'Account is {u.status.lower().replace("_"," ")}')
 u.last_login_at=datetime.now(timezone.utc); db.commit(); return {'access_token':create_access_token(u.id,u.role),'user':u}
@r.get('/me',response_model=UserOut)
def me(u=Depends(current_user)): return u
