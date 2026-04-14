"""
Job scraper module.

Primary source : SerpAPI Google Jobs  (covers LinkedIn, Indeed, Naukri, Instahyre …)
Supplementary  : WellFound (public page)  |  Hirist (public page)

SerpAPI budget per run: 2 Google-Jobs queries  (≈14/week, well inside 250-free-tier)
"""

import re
import requests
from bs4 import BeautifulSoup
from typing import Optional
from datetime import datetime

from config import (
    SERPAPI_KEY, SEARCH_TERMS,
    PRIMARY_SKILLS, SECONDARY_SKILLS,
    LOCATION_PRIORITY, LOCATION_ALIASES, REMOTE_PRIORITY, SKIP_LOCATION_SCORE,
    JOB_TYPE_PRIORITY, SKIP_JOB_TYPE_SCORE,
    SOURCE_PRIORITY, GOOGLE_JOBS_PAGES,
    YOE_MIN_ACCEPTABLE, YOE_MAX_ACCEPTABLE,
)

# Indian cities that are explicitly NOT in the preferred list.
# If a job location matches one of these and no preferred city is also present,
# the job is hard-filtered out.
_NON_PREFERRED_CITIES = [
    "chennai", "madras", "kolkata", "calcutta", "ahmedabad", "jaipur",
    "lucknow", "kochi", "cochin", "coimbatore", "vizag", "visakhapatnam",
    "bhopal", "indore", "nagpur", "surat", "vadodara", "baroda",
    "thiruvananthapuram", "trivandrum", "mysuru", "mysore",
]

# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def calculate_match_score(text: str, title: str = "") -> float:
    """
    Returns a 0-1 float representing how well the job matches Arpit's profile.
    Primary-skill matches are weighted 70 %, secondary 30 %.
    A +0.25 title boost is applied when the job title contains a primary skill,
    since title matches are a much stronger quality signal than description mentions.
    """
    low = text.lower()
    primary_hits   = sum(1 for s in PRIMARY_SKILLS   if s in low)
    secondary_hits = sum(1 for s in SECONDARY_SKILLS if s in low)

    # Normalise against a "reasonable" ceiling rather than the full list
    primary_score   = min(primary_hits   / max(len(PRIMARY_SKILLS)   * 0.4, 1), 1.0)
    secondary_score = min(secondary_hits / max(len(SECONDARY_SKILLS) * 0.3, 1), 1.0)

    base = 0.7 * primary_score + 0.3 * secondary_score

    # Title boost: primary skill in the job title is a strong relevance signal
    title_boost = 0.25 if any(s in title.lower() for s in PRIMARY_SKILLS) else 0.0

    return round(min(base + title_boost, 1.0), 2)


def extract_yoe(text: str) -> Optional[tuple[int, int]]:
    """
    Returns (min_years, max_years) or None.
    Handles patterns like "3-5 years", "5+ years", "minimum 4 years", etc.
    """
    low = text.lower()
    patterns = [
        r'(\d+)\s*[-–to]+\s*(\d+)\s*(?:years?|yrs?)',   # 3-5 years / 3 to 5 years
        r'(\d+)\+\s*(?:years?|yrs?)',                     # 5+ years
        r'minimum\s+(\d+)\s*(?:years?|yrs?)',             # minimum 4 years
        r'(\d+)\s*(?:years?|yrs?)\s*(?:of\s*)?(?:exp|experience)', # 4 years experience
    ]
    for pattern in patterns:
        m = re.search(pattern, low)
        if m:
            g = [int(x) for x in m.groups() if x is not None]
            if len(g) == 2:
                return (g[0], g[1])
            if len(g) == 1:
                return (g[0], g[0] + 2)
    return None


def get_location_priority(location_str: str) -> int:
    """
    Returns a priority integer for the given location string.
    Returns SKIP_LOCATION_SCORE for jobs in known non-preferred Indian cities.
    Vague locations ("India", "Pan India") are treated as flexible and pass through.
    """
    low = location_str.lower()

    if any(kw in low for kw in ("remote", "work from home", "wfh")):
        return REMOTE_PRIORITY

    # Check preferred cities via aliases first, then direct match
    for alias, canonical in LOCATION_ALIASES.items():
        if alias in low:
            return LOCATION_PRIORITY[canonical]
    for city, priority in LOCATION_PRIORITY.items():
        if city.lower() in low:
            return priority

    # Hard-filter known non-preferred Indian cities
    if any(city in low for city in _NON_PREFERRED_CITIES):
        return SKIP_LOCATION_SCORE

    # Vague location ("India", empty, etc.) — include but deprioritise
    return REMOTE_PRIORITY + 1


def get_job_type_info(text: str) -> tuple[int, str]:
    """
    Returns (priority, label).
    priority == SKIP_JOB_TYPE_SCORE  →  job should be discarded (more than 5-day week).
    """
    low = text.lower()

    # Hard filter: more than 5-day work week
    if re.search(
        r'6[\s-]*day|six[\s-]*day'           # "6 day", "6-day", "six day"
        r'|mon(?:day)?\s*(?:to|-)\s*sat(?:urday)?'  # "Mon to Sat", "Monday-Saturday"
        r'|5\.5\s*days?',                    # "5.5 days"
        low,
    ):
        return (SKIP_JOB_TYPE_SCORE, "skip")

    for keyword, priority in sorted(JOB_TYPE_PRIORITY.items(), key=lambda x: x[1]):
        if keyword in low:
            labels = {0: "Hybrid", 1: "Remote", 2: "On-site"}
            return (priority, labels[priority])

    return (3, "Unknown")   # Fallback — not discarded, just deprioritised


def get_source_info(apply_options: list) -> tuple[int, str]:
    """
    Inspects the apply_options list from a Google Jobs result and returns
    (source_priority, source_label) based on SOURCE_PRIORITY.
    Falls back to ("Google Jobs", len(SOURCE_PRIORITY)) if no known platform matched.
    """
    _labels = {
        "linkedin":  "LinkedIn",
        "naukri":    "Naukri",
        "instahyre": "Instahyre",
        "hirist":    "Hirist",
        "indeed":    "Indeed",
        "wellfound": "WellFound",
        "angellist": "WellFound",
    }
    for opt in apply_options:
        combined = f"{opt.get('title', '')} {opt.get('link', '')}".lower()
        for key, priority in sorted(SOURCE_PRIORITY.items(), key=lambda x: x[1]):
            if key in combined:
                return (priority, _labels.get(key, key.title()))
    return (len(SOURCE_PRIORITY), "Google Jobs")


def is_product_company(text: str) -> bool:
    low = text.lower()
    product_kw  = ["saas", "product company", "product-based", "software product",
                   "platform", "startup", "b2b", "b2c", "own product"]
    service_kw  = ["consulting", "outsourcing", "staffing", "it services",
                   "body shop", "service-based", "services company"]
    return sum(1 for k in product_kw if k in low) >= sum(1 for k in service_kw if k in low)


# ---------------------------------------------------------------------------
# SerpAPI — Google Jobs  (primary source, covers most platforms)
# ---------------------------------------------------------------------------

def scrape_google_jobs() -> list[dict]:
    """
    Fetches GOOGLE_JOBS_PAGES pages (10 results each) from SerpAPI Google Jobs.
    All search terms are combined into one OR query to minimise credit usage.
    Cost: GOOGLE_JOBS_PAGES credits/day.
    """
    combined_terms = " OR ".join(f'"{t}"' for t in SEARCH_TERMS)
    base_params = {
        "engine":  "google_jobs",
        "q":       f"({combined_terms}) India",
        "chips":   "date_posted:3days",
        "hl":      "en",
        "api_key": SERPAPI_KEY,
    }

    raw_results: list[dict] = []
    for page in range(GOOGLE_JOBS_PAGES):
        params = {**base_params, "start": page * 10}
        try:
            resp = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            print(f"    [Google Jobs] API error (page {page + 1}): {exc}")
            break

        page_results = data.get("jobs_results", [])
        raw_results.extend(page_results)
        print(f"    [Google Jobs] Page {page + 1}: {len(page_results)} results")

        # Stop early if Google returned fewer results than a full page
        if len(page_results) < 10:
            break

    jobs: list[dict] = []
    for raw in raw_results:
        desc      = raw.get("description", "")
        title     = raw.get("title", "")
        company   = raw.get("company_name", "")
        location  = raw.get("location", "")
        full_text = f"{title} {company} {desc} {location}"

        # --- Hard filters ---
        loc_priority = get_location_priority(location)
        if loc_priority == SKIP_LOCATION_SCORE:
            continue

        job_type_priority, job_type_label = get_job_type_info(full_text)
        if job_type_priority == SKIP_JOB_TYPE_SCORE:
            continue

        yoe = extract_yoe(desc)
        if yoe and (yoe[1] < YOE_MIN_ACCEPTABLE or yoe[0] > YOE_MAX_ACCEPTABLE):
            continue

        match_score = calculate_match_score(full_text, title)
        if match_score < 0.25:          # Low relevance — skip
            continue

        # --- Source platform & best apply link ---
        apply_options = raw.get("apply_options", [])
        source_priority, source_label = get_source_info(apply_options)
        job_link = next((o.get("link", "") for o in apply_options if o.get("link")), "")

        jobs.append({
            "company_name":       company,
            "title":              title,
            "location":           location,
            "yoe":                f"{yoe[0]}-{yoe[1]} yrs" if yoe else "Not specified",
            "link":               job_link,
            "applied":            "No",
            "hr_contact":         "",
            "match_score":        match_score,
            "is_product_company": is_product_company(full_text),
            "job_type_priority":  job_type_priority,
            "job_type_label":     job_type_label,
            "location_priority":  loc_priority,
            "source":             source_label,
            "source_priority":    source_priority,
            "description":        desc[:600],
        })

    return jobs


# ---------------------------------------------------------------------------
# WellFound  (startup-heavy, usually product companies)
# ---------------------------------------------------------------------------

_WELLFOUND_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def scrape_wellfound() -> list[dict]:
    """
    Scrapes WellFound's public job listing page for Flutter roles in India.
    WellFound is server-side rendered enough for BeautifulSoup on the search page.
    """
    url = "https://wellfound.com/jobs?q=flutter&l=India"
    try:
        resp = requests.get(url, headers=_WELLFOUND_HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        print(f"    [WellFound] Request failed: {exc}")
        return []

    soup  = BeautifulSoup(resp.text, "lxml")
    jobs: list[dict] = []

    # WellFound renders job cards with role links under company blocks
    for anchor in soup.find_all("a", href=re.compile(r"/jobs/")):
        title = anchor.get_text(strip=True)
        if not any(kw in title.lower() for kw in ["flutter", "mobile", "dart", "android", "ios"]):
            continue

        href = anchor.get("href", "")
        link = href if href.startswith("http") else f"https://wellfound.com{href}"

        # Try to find company name — usually a parent heading
        company_tag = anchor.find_parent(["section", "div"])
        company_name = ""
        if company_tag:
            h_tag = company_tag.find(["h2", "h3", "h4"])
            if h_tag:
                company_name = h_tag.get_text(strip=True)

        match_score = calculate_match_score(f"{title} {company_name}", title)

        jobs.append({
            "company_name":      company_name,
            "title":             title,
            "location":          "India",
            "yoe":               "Not specified",
            "link":              link,
            "applied":           "No",
            "hr_contact":        "",
            "match_score":       match_score,
            "is_product_company": True,   # WellFound = mostly product/startup
            "job_type_priority": 1,       # WellFound skews remote/hybrid
            "job_type_label":    "Remote/Hybrid",
            "location_priority": REMOTE_PRIORITY,
            "source":            "WellFound",
            "source_priority":   SOURCE_PRIORITY.get("wellfound", len(SOURCE_PRIORITY)),
            "description":       "",
        })

    return jobs


# ---------------------------------------------------------------------------
# Hirist
# ---------------------------------------------------------------------------

_HIRIST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


def scrape_hirist() -> list[dict]:
    """Scrapes Hirist's public Flutter developer job listing page."""
    url = "https://www.hirist.tech/j/flutter-developer-jobs"
    try:
        resp = requests.get(url, headers=_HIRIST_HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        print(f"    [Hirist] Request failed: {exc}")
        return []

    soup  = BeautifulSoup(resp.text, "lxml")
    jobs: list[dict] = []

    # Hirist job cards vary by version; try multiple selectors
    cards = (
        soup.find_all("div", class_=re.compile(r"job[-_]?card|jobCard", re.I))
        or soup.find_all("article")
        or soup.find_all("li", class_=re.compile(r"job", re.I))
    )

    for card in cards:
        # Title
        title_tag = card.find(["h2", "h3", "a"], class_=re.compile(r"title|position|role", re.I))
        title = title_tag.get_text(strip=True) if title_tag else ""

        if not title or not any(kw in title.lower() for kw in ["flutter", "mobile", "dart"]):
            continue

        # Company
        co_tag = card.find(["span", "div", "p"], class_=re.compile(r"company|employer", re.I))
        company_name = co_tag.get_text(strip=True) if co_tag else ""

        # Link
        link_tag = card.find("a", href=True)
        href = link_tag["href"] if link_tag else ""
        link = href if href.startswith("http") else f"https://www.hirist.tech{href}"

        # YOE
        exp_tag = card.find(text=re.compile(r"\d+\s*[-–]\s*\d+\s*(?:yrs?|years?)", re.I))
        yoe_str = exp_tag.strip() if exp_tag else "Not specified"

        match_score = calculate_match_score(f"{title} {company_name}", title)

        jobs.append({
            "company_name":      company_name,
            "title":             title,
            "location":          "India",
            "yoe":               yoe_str,
            "link":              link,
            "applied":           "No",
            "hr_contact":        "",
            "match_score":       match_score,
            "is_product_company": False,   # Unknown
            "job_type_priority": 2,
            "job_type_label":    "Unknown",
            "location_priority": REMOTE_PRIORITY + 1,
            "source":            "Hirist",
            "source_priority":   SOURCE_PRIORITY.get("hirist", len(SOURCE_PRIORITY)),
            "description":       "",
        })

    return jobs


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

def get_all_jobs() -> list[dict]:
    """
    Pulls jobs from all sources, deduplicates by link, and returns them
    sorted by relevance (product company > match score > location > job type).
    """
    all_jobs: list[dict] = []
    seen_links: set[str] = set()

    def _add(jobs: list[dict], label: str):
        new = [j for j in jobs if j["link"] and j["link"] not in seen_links]
        for j in new:
            seen_links.add(j["link"])
        all_jobs.extend(new)
        print(f"    [{label}] {len(new)} new jobs")

    # --- Google Jobs — single combined OR query (1 SerpAPI credit) ---
    print("  Querying Google Jobs via SerpAPI…")
    _add(scrape_google_jobs(), "Google Jobs")

    # --- Supplementary scrapers ---
    print("  Scraping WellFound…")
    _add(scrape_wellfound(), "WellFound")

    print("  Scraping Hirist…")
    _add(scrape_hirist(), "Hirist")

    # --- Sort ---
    all_jobs.sort(key=lambda j: (
        0 if j["is_product_company"] else 1,        # product first
        -j["match_score"],                           # higher score first
        j["location_priority"],                      # Bengaluru before Mumbai
        j["job_type_priority"],                      # hybrid before WFO
        j.get("source_priority", len(SOURCE_PRIORITY)),  # LinkedIn before Naukri, etc.
    ))

    print(f"\n  Total unique jobs: {len(all_jobs)}")
    return all_jobs
