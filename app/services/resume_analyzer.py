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

ROLE_SKILLS = {
    "golang": [
        "go", "golang", "microservices", "rest", "rest api", "grpc",
        "postgresql", "mysql", "redis", "kafka", "docker", "kubernetes",
        "aws", "ci/cd", "git", "testing", "distributed systems", "linux",
    ],
    "backend": [
        "go", "golang", "java", "python", "microservices", "rest", "api",
        "grpc", "postgresql", "mysql", "redis", "kafka", "docker",
        "kubernetes", "aws", "ci/cd", "git", "testing", "distributed systems",
    ],
    "software engineer": [
        "programming", "algorithms", "data structures", "api", "testing",
        "git", "sql", "cloud", "docker", "ci/cd", "system design",
    ],
    "frontend": [
        "javascript", "typescript", "react", "html", "css", "rest", "git",
        "testing", "responsive", "accessibility",
    ],
    "full stack": [
        "javascript", "typescript", "react", "node", "api", "sql", "git",
        "docker", "cloud", "testing", "html", "css",
    ],
    "devops": [
        "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "linux",
        "ci/cd", "jenkins", "github actions", "monitoring", "observability",
    ],
    "data engineer": [
        "python", "sql", "spark", "airflow", "kafka", "etl", "data pipelines",
        "aws", "azure", "gcp", "snowflake", "databricks",
    ],
}

WEAK_STARTS = re.compile(r"^(worked|helped|responsible for|involved in|assisted|participated)", re.I)
ACTION_WORDS = re.compile(
    r"\b(developed|built|designed|implemented|optimized|automated|led|migrated|reduced|improved|"
    r"increased|delivered|created|architected|integrated|deployed|maintained|scaled|launched|"
    r"engineered|streamlined)\b", re.I
)

def _sections(text):
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    found, current = {}, None
    for line in lines:
        key = line.lower().strip(" :-")
        match = next((k for k, v in SECTION_ALIASES.items() if key in v), None)
        if match:
            current = match
            found.setdefault(current, [])
        elif current:
            found[current].append(line)
    return found

def _bullets(text):
    return [x.strip(" •-*	") for x in text.splitlines() if len(x.strip(" •-*	")) >= 25]

def _role_key(target_roles):
    value = " ".join(target_roles).lower()
    if "golang" in value or re.search(r"\bgo\b", value) or "go developer" in value:
        return "golang"
    for key in ROLE_SKILLS:
        if key != "golang" and key in value:
            return key
    return "software engineer"

def _term_present(term, text):
    if term in {"go", "api"}:
        return bool(re.search(rf"\b{re.escape(term)}\b", text))
    return term in text

def _job_market_skills(jobs):
    counts = Counter()
    for job in jobs or []:
        text = " ".join(str(job.get(k) or "") for k in ("title", "description", "company", "location")).lower()
        for skill in set(sum(ROLE_SKILLS.values(), [])):
            if _term_present(skill, text):
                counts[skill] += 1
    total = len(jobs or [])
    return [
        {"skill": skill, "frequency": round(counts[skill] / total * 100)}
        for skill in counts
        if counts[skill] > 0
    ]

def analyze_resume(text, preferences=None, jobs=None):
    text = text or ""
    lower = text.lower()
    preferences = preferences or {}
    target_titles = preferences.get("job_titles") or []
    role = _role_key(target_titles)
    role_skills = ROLE_SKILLS.get(role, ROLE_SKILLS["software engineer"])
    sections = _sections(text)
    bullets = _bullets(text)
    issues, strengths = [], []

    missing = [s for s in ("experience", "education", "skills") if s not in sections]
    for s in missing:
        issues.append({"severity": "HIGH", "category": "Structure", "title": f"Add a {s.title()} section",
                       "detail": f"The resume does not clearly contain a standard {s.title()} section."})

    words = len(text.split())
    if words < 180:
        issues.append({"severity": "HIGH", "category": "Content", "title": "Resume may be too short",
                       "detail": "Add relevant experience, projects, or skills you genuinely have; avoid filler."})
    if words > 1100:
        issues.append({"severity": "MEDIUM", "category": "Content", "title": "Reduce low-relevance content",
                       "detail": "Prioritize evidence that supports the target role and remove repetition."})

    weak = [b for b in bullets if WEAK_STARTS.search(b)]
    if weak:
        issues.append({"severity": "HIGH", "category": "Impact", "title": "Replace responsibility-only bullets",
                       "detail": f"{len(weak)} bullet(s) use passive responsibility language. Lead with the action, technology, scale, and outcome."})

    action_ratio = sum(bool(ACTION_WORDS.search(b)) for b in bullets) / max(1, len(bullets))
    if action_ratio < .35:
        issues.append({"severity": "MEDIUM", "category": "Impact", "title": "Increase accomplishment language",
                       "detail": "Use strong verbs and explain what changed because of your work, without inventing results."})

    metric_count = len(re.findall(r"\b\d+(?:\.\d+)?%?\b", text))
    if metric_count < 3:
        issues.append({"severity": "MEDIUM", "category": "Impact", "title": "Add measurable impact where truthful",
                       "detail": "Where you have real evidence, quantify latency, throughput, scale, reliability, cost, delivery time, or business impact."})

    emails = len(re.findall(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.I))
    phones = len(re.findall(r"(?:\+?\d[\d\s().-]{7,}\d)", text))
    if not emails or not phones:
        issues.append({"severity": "HIGH", "category": "ATS", "title": "Complete professional contact details",
                       "detail": "Make sure the resume has a professional email and phone number in a clearly parseable header."})
    if "linkedin" not in lower:
        issues.append({"severity": "LOW", "category": "Completeness", "title": "Consider adding LinkedIn",
                       "detail": "If you maintain a professional LinkedIn profile, include it in the header."})

    role_matches = [s for s in role_skills if _term_present(s, lower)]
    role_missing = [s for s in role_skills if not _term_present(s, lower)]
    alignment = round(len(role_matches) / max(1, len(role_skills)) * 100)
    if target_titles and alignment < 75:
        preview = ", ".join(role_missing[:6])
        issues.append({"severity": "HIGH" if alignment < 55 else "MEDIUM", "category": "Job Alignment",
                       "title": f"Strengthen {target_titles[0]} alignment",
                       "detail": f"Your resume clearly demonstrates {len(role_matches)} of {len(role_skills)} common role signals. Consider adding truthful evidence for: {preview}."})

    market = _job_market_skills(jobs)
    market_map = {x["skill"]: x["frequency"] for x in market}
    market_gaps = [x for x in market if x["frequency"] >= 30 and not _term_present(x["skill"], lower)]
    if market_gaps:
        top = ", ".join(x["skill"] for x in sorted(market_gaps, key=lambda x: -x["frequency"])[:5])
        issues.append({"severity": "MEDIUM", "category": "Market Alignment", "title": "Cover skills appearing in target jobs",
                       "detail": f"Among {len(jobs)} discovered target-role jobs, these commonly requested skills are not clearly present in your resume: {top}. Add them only if you genuinely have the experience."})

    if not sections.get("summary"):
        issues.append({"severity": "MEDIUM", "category": "Positioning", "title": "Add a focused professional summary",
                       "detail": f"Open with a concise summary that positions you for {target_titles[0] if target_titles else 'your target role'} and highlights your strongest relevant technologies and outcomes."})

    # Scores reward evidence and penalize concrete issues; role alignment is deliberately role-specific.
    ats = 100
    content = 100
    impact = 100
    readability = 100
    for i in issues:
        penalty = {"HIGH": 12, "MEDIUM": 7, "LOW": 3}[i["severity"]]
        if i["category"] == "ATS":
            ats -= penalty
        elif i["category"] in ("Impact",):
            impact -= penalty
        elif i["category"] in ("Content",):
            content -= penalty
        else:
            readability -= penalty

    scores = {
        "ats": max(0, min(100, ats)),
        "content": max(0, min(100, content)),
        "impact": max(0, min(100, impact)),
        "readability": max(0, min(100, readability)),
        "job_alignment": max(0, min(100, alignment)),
    }
    scores["overall"] = round(
        scores["job_alignment"] * .30 + scores["ats"] * .18 + scores["content"] * .17 +
        scores["impact"] * .20 + scores["readability"] * .15
    )

    for s in ("experience", "education", "skills"):
        if s in sections:
            strengths.append(f"Clear {s.title()} section")
    if len(role_matches) >= max(3, len(role_skills) // 3):
        strengths.append(f"Strong technical evidence for {target_titles[0] if target_titles else role}")
    if metric_count >= 5:
        strengths.append("Multiple measurable details strengthen credibility")
    if action_ratio >= .5:
        strengths.append("Good use of accomplishment-focused action language")

    quick_fixes = []

    # Provide copy/replace-ready edits. These preserve the candidate's existing
    # facts rather than inventing achievements or metrics.
    for bullet in weak[:8]:
        replacement = re.sub(r"^responsible for\\s+", "Owned ", bullet, flags=re.I)
        replacement = re.sub(r"^worked on\\s+", "Contributed to ", replacement, flags=re.I)
        replacement = re.sub(r"^helped\\s+", "Supported ", replacement, flags=re.I)
        replacement = re.sub(r"^assisted\\s+", "Supported ", replacement, flags=re.I)
        replacement = re.sub(r"^participated in\\s+", "Contributed to ", replacement, flags=re.I)
        replacement = re.sub(r"^involved in\\s+", "Contributed to ", replacement, flags=re.I)
        if replacement != bullet:
            quick_fixes.append({
                "type": "BULLET_REWRITE",
                "category": "Impact",
                "original": bullet,
                "replacement": replacement,
                "note": "This keeps the original claim but uses clearer, accomplishment-oriented language. Add a real outcome or metric if you have one."
            })

    if "summary" not in sections:
        role_name = target_titles[0] if target_titles else "Software Engineer"
        skill_text = ", ".join(role_matches[:6])
        template = (
            f"{role_name} with experience in {skill_text}. "
            "Experienced in building, improving, and supporting production software systems. "
            "Focused on delivering reliable, scalable solutions and measurable business impact."
            if skill_text else
            f"{role_name} with experience building and supporting production software systems. "
            "Focused on delivering reliable, scalable solutions and measurable business impact."
        )
        quick_fixes.append({
            "type": "SUMMARY_TEMPLATE",
            "category": "Positioning",
            "original": "",
            "replacement": template,
            "note": "Use this as a starting point and edit it so every statement is true for your actual experience."
        })

    if market_gaps:
        quick_fixes.append({
            "type": "SKILL_GAP",
            "category": "Market Alignment",
            "original": "",
            "replacement": "Add only the following skills to your Skills section if you genuinely have hands-on experience: " +
                           ", ".join(x["skill"] for x in sorted(market_gaps, key=lambda x: -x["frequency"])[:8]),
            "note": "These skills appeared frequently in the target jobs JobPilot analyzed; do not add skills you cannot support in an interview."
        })

    recommendations = []
    for item in sorted(issues, key=lambda x: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[x["severity"]]):
        recommendations.append({
            "priority": item["severity"],
            "category": item["category"],
            "title": item["title"],
            "action": item["detail"],
        })

    return {
        "scores": scores,
        "target_role": target_titles[0] if target_titles else "Software Engineer",
        "role_family": role,
        "issues": issues,
        "strengths": strengths,
        "recommendations": recommendations,
        "quick_fixes": quick_fixes,
        "role_skills": [{"skill": s, "present": s in role_matches} for s in role_skills],
        "market_skills": sorted(market, key=lambda x: -x["frequency"])[:15],
        "stats": {
            "word_count": words,
            "bullet_count": len(bullets),
            "sections": list(sections),
            "quantified_items": metric_count,
            "target_jobs_analyzed": len(jobs or []),
        },
    }
