import jwt
from fastapi import Depends,HTTPException
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User
from app.security import decode_token
bearer=HTTPBearer(auto_error=False)
def current_user(c:HTTPAuthorizationCredentials=Depends(bearer),db:Session=Depends(get_db)):
 if not c: raise HTTPException(401,'Authentication required')
 try: uid=int(decode_token(c.credentials)['sub'])
 except (jwt.PyJWTError,KeyError,ValueError): raise HTTPException(401,'Invalid or expired token')
 u=db.get(User,uid)
 if not u: raise HTTPException(401,'User not found')
 return u
def active_user(u:User=Depends(current_user)):
 if u.status!='ACTIVE': raise HTTPException(403,'Account is not active')
 return u
def admin_user(u:User=Depends(current_user)):
 if u.role!='ADMIN' or u.status!='ACTIVE': raise HTTPException(403,'Admin access required')
 return u
