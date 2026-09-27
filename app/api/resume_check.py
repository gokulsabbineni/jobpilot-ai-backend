from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Resume
from app.models_resume_check import ResumeCheck
from app.auth import active_user
from app.services.resume_analyzer import analyze_resume

r=APIRouter(prefix="/api/user/resume-check",tags=["resume-check"])

def _serialize(x):
    return {"id":x.id,"resume_id":x.resume_id,"overall_score":x.overall_score,"ats_score":x.ats_score,"content_score":x.content_score,"impact_score":x.impact_score,"readability_score":x.readability_score,"job_alignment_score":x.job_alignment_score,"analysis":x.analysis,"updated_at":x.updated_at}

@r.get("")
def get_check(db:Session=Depends(get_db),u=Depends(active_user)):
    x=db.query(ResumeCheck).filter(ResumeCheck.user_id==u.id).first()
    if not x: return None
    return _serialize(x)

@r.post("/analyze")
def run_check(db:Session=Depends(get_db),u=Depends(active_user)):
    resume=db.query(Resume).filter(Resume.user_id==u.id).first()
    if not resume or not resume.content_text:
        raise HTTPException(400,"Upload a resume with readable text before running Resume Check.")
    prefs=u.preferences
    pref_data={"job_titles":prefs.job_titles if prefs else []}
    analysis=analyze_resume(resume.content_text,pref_data)
    x=db.query(ResumeCheck).filter(ResumeCheck.user_id==u.id).first()
    if not x:
        x=ResumeCheck(user_id=u.id,resume_id=resume.id)
        db.add(x)
    x.resume_id=resume.id
    s=analysis["scores"]
    x.overall_score=s["overall"]; x.ats_score=s["ats"]; x.content_score=s["content"]; x.impact_score=s["impact"]; x.readability_score=s["readability"]; x.job_alignment_score=s["job_alignment"]; x.analysis=analysis
    db.commit(); db.refresh(x)
    return _serialize(x)
