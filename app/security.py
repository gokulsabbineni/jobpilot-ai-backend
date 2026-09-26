import hashlib,hmac,base64,os,jwt
from datetime import datetime,timedelta,timezone
from app.config import settings
def hash_password(p):
 s=os.urandom(16); i=120000; d=hashlib.pbkdf2_hmac('sha256',p.encode(),s,i); return f'pbkdf2_sha256${i}${base64.b64encode(s).decode()}${base64.b64encode(d).decode()}'
def verify_password(p,e):
 try:
  _,i,s,d=e.split('$'); a=hashlib.pbkdf2_hmac('sha256',p.encode(),base64.b64decode(s),int(i)); return hmac.compare_digest(a,base64.b64decode(d))
 except: return False
def create_access_token(uid,role): return jwt.encode({'sub':str(uid),'role':role,'exp':datetime.now(timezone.utc)+timedelta(minutes=settings.access_token_expire_minutes)},settings.secret_key,algorithm='HS256')
def decode_token(t): return jwt.decode(t,settings.secret_key,algorithms=['HS256'])
