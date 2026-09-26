import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from app.services.discovery import infer_job_type, parse_datetime


class CareerPageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.jsonld = []
        self.links = []
        self._script = False
        self._buffer = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag.lower() == "script" and "ld+json" in str(attrs.get("type", "")).lower():
            self._script = True
            self._buffer = []
        elif tag.lower() == "a" and attrs.get("href"):
            self.links.append(attrs["href"])

    def handle_data(self, data):
        if self._script:
            self._buffer.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self._script:
            self.jsonld.append("".join(self._buffer))
            self._script = False
            self._buffer = []


def jsonld_jobs(value):
    found = []
    if isinstance(value, list):
        for item in value:
            found.extend(jsonld_jobs(item))
    elif isinstance(value, dict):
        types = value.get("@type")
        types = types if isinstance(types, list) else [types]
        if any(str(x).lower() == "jobposting" for x in types):
            found.append(value)
        for key in ("@graph", "itemListElement", "mainEntity", "mainEntityOfPage"):
            if key in value:
                found.extend(jsonld_jobs(value[key]))
    return found


def to_payload(item, page_url):
    org = item.get("hiringOrganization") or {}
    loc = item.get("jobLocation")
    if isinstance(loc, list):
        values = []
        for entry in loc:
            address = (entry or {}).get("address", {}) if isinstance(entry, dict) else {}
            values.append(", ".join(str(x) for x in (
                address.get("addressLocality"), address.get("addressRegion"), address.get("addressCountry")
            ) if x))
        location = " | ".join(x for x in values if x)
    elif isinstance(loc, dict):
        address = loc.get("address", {})
        location = ", ".join(str(x) for x in (
            address.get("addressLocality"), address.get("addressRegion"), address.get("addressCountry")
        ) if x)
    else:
        location = str(loc or "")

    employment = item.get("employmentType")
    if isinstance(employment, list):
        employment = employment[0] if employment else None

    salary = item.get("baseSalary") or {}
    value = salary.get("value", {}) if isinstance(salary, dict) else {}
    return {
        "provider": "CAREER_PAGE",
        "external_id": str(item.get("identifier") or item.get("url") or page_url),
        "company": org.get("name") or "Unknown Company",
        "title": item.get("title") or "Untitled",
        "description": item.get("description") or "",
        "location": location or "United States",
        "job_type": str(employment or "").upper().replace("-", "_") or infer_job_type(str(item.get("description") or "")),
        "remote": "remote" in str(item.get("jobLocationType") or "").lower() or "remote" in location.lower(),
        "salary_min": value.get("minValue") if isinstance(value, dict) else None,
        "salary_max": value.get("maxValue") if isinstance(value, dict) else None,
        "url": item.get("url") or page_url,
        "posted_at": parse_datetime(item.get("datePosted")),
        "source_url": page_url,
        "raw_data": item,
    }


async def crawl(client, url, search=None, max_links=20):
    response = await client.get(url)
    response.raise_for_status()
    parser = CareerPageParser()
    parser.feed(response.text)

    jobs = []
    for raw in parser.jsonld:
        try:
            jobs.extend(to_payload(x, str(response.url)) for x in jsonld_jobs(json.loads(raw)))
        except (json.JSONDecodeError, TypeError):
            continue

    if not jobs:
        base = str(response.url)
        host = urlsplit(base).netloc.lower()
        links = []
        for href in parser.links:
            absolute = urljoin(base, href)
            parts = urlsplit(absolute)
            path = (parts.path + " " + parts.query).lower()
            if parts.netloc.lower() == host and any(x in path for x in ("job", "career", "position", "opening", "vacanc")):
                links.append(absolute)
        for child in links[:max_links]:
            try:
                child_response = await client.get(child)
                if child_response.status_code >= 400:
                    continue
                child_parser = CareerPageParser()
                child_parser.feed(child_response.text)
                for raw in child_parser.jsonld:
                    try:
                        jobs.extend(to_payload(x, str(child_response.url)) for x in jsonld_jobs(json.loads(raw)))
                    except (json.JSONDecodeError, TypeError):
                        continue
            except Exception:
                continue
            if len(jobs) >= 100:
                break

    if search:
        terms = [x.lower() for x in re.findall(r"[A-Za-z0-9]+", search) if len(x) > 2]
        jobs = [
            x for x in jobs
            if any(term in (x["title"] + " " + x["description"]).lower() for term in terms)
        ]
    return jobs[:100]
