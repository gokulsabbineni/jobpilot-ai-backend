from pathlib import Path
from fastapi import APIRouter,Depends,UploadFile,File,HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import active_user
from app.models import Resume
from app.config import settings
r=APIRouter(prefix='/api/user/resume',tags=['resume'])
@r.get('')
def get_resume(u=Depends(active_user)): return u.resume
@r.post('')
async def upload(file:UploadFile=File(...),db:Session=Depends(get_db),u=Depends(active_user)):
 name=Path(file.filename or '').name
 if Path(name).suffix.lower() not in {'.pdf','.docx','.txt'}: raise HTTPException(400,'Only PDF, DOCX and TXT files are supported')
 data=await file.read()
 if len(data)>10*1024*1024: raise HTTPException(413,'File too large')
 folder=Path(settings.storage_dir); folder.mkdir(parents=True,exist_ok=True); path=folder/f'user_{u.id}_{name}'; path.write_bytes(data)
 x=u.resume or Resume(user_id=u.id,file_name=name); x.file_name=name; x.file_path=str(path); x.parsed_profile={'skills':[],'experience':[],'education':[]}
 if not u.resume: db.add(x)
 db.commit(); db.refresh(x); return x
