import re
from collections import Counter

SECTION_ALIASES = {
    "summary": ("summary", "professional summary", "profile", "objective"),
    "experience": ("experience", "work experience", "professional experience", "employment"),
    "education": ("education", "academic background"),
    "skills": ("skills", "technical skills", "core skills", "technologies"),
    "projects": ("projects", "selected projects"),
    "certifications": ("certifications", "certificates"),
}

WEAK_STARTS = re.compile(r"^(worked|helped|responsible for|involved in|assisted|participated)", re.I)
ACTION_WORDS = re.compile(r"\b(developed|built|designed|implemented|optimized|automated|led|migrated|reduced|improved|increased|delivered|created|architected|integrated|deployed|maintained)\b", re.I)

def _sections(text):
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    found={}
    current=None
    for line in lines:
        key=line.lower().strip(" :-")
        match=next((k for k,v in SECTION_ALIASES.items() if key in v),None)
        if match:
            current=match; found.setdefault(current,[])
        elif current:
            found[current].append(line)
    return found

def _bullets(text):
    return [x.strip(" •-*\t") for x in text.splitlines() if len(x.strip(" •-*\t")) >= 25]

def analyze_resume(text, preferences=None):
    text=text or ""
    lower=text.lower()
    sections=_sections(text)
    bullets=_bullets(text)
    issues=[]
    strengths=[]
    required=("experience","education","skills")
    missing=[s for s in required if s not in sections]
    for s in missing:
        issues.append({"severity":"HIGH","category":"Structure","title":f"Add a {s.title()} section","detail":f"The resume does not clearly contain a standard {s.title()} section."})
    if len(text.split()) < 180:
        issues.append({"severity":"HIGH","category":"Content","title":"Resume may be too short","detail":"The resume contains relatively little searchable content. Add relevant experience, projects, or skills you genuinely have."})
    if len(text.split()) > 1100:
        issues.append({"severity":"MEDIUM","category":"Content","title":"Resume may be too long","detail":"Consider removing repetitive or low-relevance content for the roles you target."})
    weak=[b for b in bullets if WEAK_STARTS.search(b)]
    if weak:
        issues.append({"severity":"HIGH","category":"Impact","title":"Strengthen responsibility-based bullets","detail":f"{len(weak)} bullet(s) begin with passive responsibility language. Rewrite them around the action, technology, and outcome."})
    action_ratio=sum(bool(ACTION_WORDS.search(b)) for b in bullets)/max(1,len(bullets))
    if action_ratio < .35:
        issues.append({"severity":"MEDIUM","category":"Impact","title":"Use stronger action language","detail":"Many bullets do not clearly state what you built, changed, automated, improved, or delivered."})
    metric_count=len(re.findall(r"\b\d+(?:\.\d+)?%?\b",text))
    if metric_count < 3:
        issues.append({"severity":"MEDIUM","category":"Impact","title":"Add measurable results where truthful","detail":"Consider adding real scale, performance, volume, time, cost, or reliability metrics to relevant accomplishments. Do not invent numbers."})
    if len(re.findall(r"@|\b(phone|email)\b",lower)) < 2:
        issues.append({"severity":"HIGH","category":"ATS","title":"Check contact information","detail":"Make sure a professional email and phone/contact method are clearly present."})
    if "linkedin" not in lower:
        issues.append({"severity":"LOW","category":"Completeness","title":"Consider adding LinkedIn","detail":"If you maintain a professional LinkedIn profile, consider including it."})
    skills_text=" ".join(sections.get("skills",[])).lower()
    target_titles=(preferences or {}).get("job_titles") or []
    title_terms=set(re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}", " ".join(target_titles).lower()))
    matched_terms=sorted(t for t in title_terms if t in lower and len(t)>2)
    if target_titles and len(matched_terms) < max(2,min(6,len(title_terms))):
        issues.append({"severity":"MEDIUM","category":"Job Alignment","title":"Align keywords with target roles","detail":"Your target job titles and resume content have limited keyword overlap. Add only skills and experience you genuinely have."})
    if "tables" in lower or "text box" in lower:
        issues.append({"severity":"LOW","category":"ATS","title":"Review complex formatting","detail":"If the document uses tables or text boxes for important information, verify that extracted text preserves the intended reading order."})
    ats=100
    content=100
    impact=100
    readability=100
    alignment=100 if not target_titles else min(100,55+len(matched_terms)*8)
    for i in issues:
        penalty={"HIGH":12,"MEDIUM":7,"LOW":3}[i["severity"]]
        if i["category"]=="ATS": ats-=penalty
        elif i["category"]=="Impact": impact-=penalty
        elif i["category"]=="Job Alignment": alignment-=penalty
        elif i["category"]=="Content": content-=penalty
        else: readability-=penalty
    scores={k:max(0,min(100,v)) for k,v in {"ats":ats,"content":content,"impact":impact,"readability":readability,"job_alignment":alignment}.items()}
    scores["overall"]=round(scores["ats"]*.2+scores["content"]*.2+scores["impact"]*.25+scores["readability"]*.15+scores["job_alignment"]*.2)
    strengths.extend([f"Clear {s.title()} section" for s in sections if s in required])
    return {"scores":scores,"issues":issues,"strengths":strengths,"stats":{"word_count":len(text.split()),"bullet_count":len(bullets),"sections":list(sections),"quantified_items":metric_count}}
