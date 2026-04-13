"""
LinkedIn profile discovery via SerpAPI Google Search.

Budget design  (250 searches / month):
┌─────────────────────────────────────────────────────────┐
│  Job search   : 1 query/day  ×  30 days  =  30/month   │
│  Profile search: 1 query/company (HR + Dev combined)    │
│  Remaining for profiles: 250 − 30 = 220/month           │
│  ≈ 7 companies/day — far more than reality ever needs   │
└─────────────────────────────────────────────────────────┘

Key decisions:
  • HR and developer profiles are fetched in ONE combined query per company
    (halved from the previous 2-query approach).
  • Remaining search count is fetched ONCE per run (not before every company).
  • A monthly-aware guard reserves budget for job searches on remaining days,
    then allocates the rest to profile searches for this run.
  • Companies are processed best-match-first so the most valuable ones are
    never cut when the budget is tight.
"""

import re
import requests
from calendar import monthrange
from datetime import date

from config import SERPAPI_KEY, get_suggested_profile_count


# ---------------------------------------------------------------------------
# Budget constants
# ---------------------------------------------------------------------------

MONTHLY_LIMIT        = 250   # SerpAPI free tier
JOB_QUERIES_PER_DAY  = 1     # One combined OR query per daily run
SAFETY_BUFFER        = 10    # Never spend the last N searches (keep as buffer)


# ---------------------------------------------------------------------------
# SerpAPI quota — fetched ONCE per run
# ---------------------------------------------------------------------------

def get_serpapi_remaining() -> int:
    """
    Calls SerpAPI's account endpoint (does NOT consume a search credit).
    Returns 9999 on failure so we don't block the run unnecessarily.
    """
    try:
        resp = requests.get(
            "https://serpapi.com/account",
            params={"api_key": SERPAPI_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return int(data.get("searches_left") or data.get("total_searches_left") or 9999)
    except Exception:
        return 9999


def compute_profile_budget() -> int:
    """
    Works out how many profile-search queries are available for THIS run.

    Logic:
      1. Fetch actual remaining searches from SerpAPI.
      2. Reserve (days_left_in_month × JOB_QUERIES_PER_DAY) for future job searches.
      3. Reserve SAFETY_BUFFER.
      4. Whatever is left can be spent on profile searches today.
      5. Each company costs exactly 1 query, so budget == max companies.
    """
    remaining = get_serpapi_remaining()

    today           = date.today()
    days_in_month   = monthrange(today.year, today.month)[1]
    days_left       = days_in_month - today.day   # excludes today (already ran job query)

    reserved_jobs   = days_left * JOB_QUERIES_PER_DAY
    available       = remaining - reserved_jobs - SAFETY_BUFFER

    print(
        f"    SerpAPI: {remaining} searches left | "
        f"{reserved_jobs} reserved for {days_left} remaining days | "
        f"{SAFETY_BUFFER} safety buffer | "
        f"{max(available, 0)} available for profiles today"
    )

    return max(available, 0)


# ---------------------------------------------------------------------------
# Core search
# ---------------------------------------------------------------------------

def _google_search(query: str, num_results: int = 10) -> list[dict]:
    """Thin SerpAPI wrapper — returns organic_results or [] on error."""
    params = {
        "engine":  "google",
        "q":       query,
        "num":     num_results,
        "hl":      "en",
        "api_key": SERPAPI_KEY,
    }
    try:
        resp = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("organic_results", [])
    except Exception as exc:
        print(f"      [SerpAPI] error: {exc}")
        return []


# ---------------------------------------------------------------------------
# Name / title parsing
# ---------------------------------------------------------------------------

def _parse_name(title: str) -> str:
    """
    LinkedIn titles:  "Priya Sharma - Senior HR at Zepto | LinkedIn"
    Returns name string or "" if parsing fails basic sanity checks.
    """
    clean = re.sub(r"\s*[|\-]\s*LinkedIn\s*$", "", title, flags=re.I).strip()
    parts = re.split(r"\s*[-–|]\s*", clean, maxsplit=1)
    candidate = parts[0].strip()
    words = candidate.split()
    if 2 <= len(words) <= 4 and re.match(r"^[A-Za-z\s\.]+$", candidate):
        return candidate
    return ""


def _parse_job_title(title: str) -> str:
    clean = re.sub(r"\s*[|\-]\s*LinkedIn\s*$", "", title, flags=re.I).strip()
    parts = re.split(r"\s*[-–|]\s*", clean, maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


_HR_KEYWORDS  = {"recruiter", "hr ", "h.r.", "talent", "people ops", "hiring", "human resource"}
_DEV_KEYWORDS = {"flutter", "mobile", "android", "ios", "dart", "developer", "engineer", "engineer"}


def _classify_role(title: str) -> str:
    """Returns 'HR/Recruiter' or 'Developer' based on job title keywords."""
    low = title.lower()
    if any(kw in low for kw in _HR_KEYWORDS):
        return "HR/Recruiter"
    return "Developer"


# ---------------------------------------------------------------------------
# Per-company profile fetch  (1 SerpAPI query)
# ---------------------------------------------------------------------------

def find_profiles_for_company(company_name: str, match_score: float) -> list[dict]:
    """
    Fetches HR + developer LinkedIn profiles for a company in a SINGLE query.

    The combined query returns a mixed result set; we classify each profile
    locally using title keywords — zero extra API cost.

    Cost: exactly 1 SerpAPI search.
    """
    total     = get_suggested_profile_count(match_score)
    # Ask for more results than needed so we have headroom after filtering
    fetch_n   = min(total * 3, 20)

    query = (
        f'site:linkedin.com/in '
        f'("recruiter" OR "HR" OR "talent acquisition" OR "people operations" '
        f'OR "flutter" OR "mobile developer" OR "android" OR "ios developer") '
        f'"{company_name}"'
    )

    results = _google_search(query, num_results=fetch_n)

    seen: set[str]     = set()
    hr_profiles: list  = []
    dev_profiles: list = []

    for r in results:
        link = r.get("link", "")
        if "linkedin.com/in/" not in link or link in seen:
            continue

        name      = _parse_name(r.get("title", ""))
        job_title = _parse_job_title(r.get("title", ""))
        if not name:
            continue

        seen.add(link)
        role_type = _classify_role(job_title)

        profile = {
            "name":         name,
            "profile_link": link,
            "company_name": company_name,
            "job_title":    job_title,
            "role_type":    role_type,
            "snippet":      r.get("snippet", ""),
        }

        if role_type == "HR/Recruiter":
            hr_profiles.append(profile)
        else:
            dev_profiles.append(profile)

    # Balanced mix: half HR, half developers, up to `total`
    hr_want  = max(1, total // 2)
    dev_want = total - hr_want

    combined = hr_profiles[:hr_want] + dev_profiles[:dev_want]

    # If one category came up short, fill from the other
    if len(combined) < total:
        extras = [p for p in (hr_profiles + dev_profiles) if p not in combined]
        combined += extras[: total - len(combined)]

    return combined[:total]


# ---------------------------------------------------------------------------
# Batch helper called by main.py
# ---------------------------------------------------------------------------

def find_profiles_for_new_jobs(
    jobs: list[dict],
    existing_companies: set[str],
) -> dict[str, list[dict]]:
    """
    Searches profiles for ALL new companies (not already in the Connections sheet),
    sorted best-match-first.

    Budget is computed ONCE at the start of this function:
      - Fetches remaining SerpAPI searches
      - Reserves credits for job searches on remaining days of the month
      - Allocates the rest to profile searches (1 credit per company)
    Stops gracefully when the budget is exhausted.

    Returns  { company_name: [profile_dict, …] }
    """
    # Collect unique new companies, deduped
    seen: set[str]    = set()
    new_jobs: list    = []
    for job in jobs:
        co = job.get("company_name", "").strip()
        if co and co not in existing_companies and co not in seen:
            seen.add(co)
            new_jobs.append(job)

    if not new_jobs:
        print("    No new companies to search.")
        return {}

    # Sort best-match first so high-value companies are never skipped on a tight budget
    new_jobs.sort(key=lambda j: -j["match_score"])

    # Compute budget ONCE (one account API call, not counted as a search)
    profile_budget = compute_profile_budget()

    if profile_budget == 0:
        print("    ⚠  No profile-search budget remaining for today. Will retry tomorrow.")
        return {}

    total_new = len(new_jobs)
    can_search = min(total_new, profile_budget)
    skipped    = total_new - can_search

    print(
        f"    {total_new} new company(s) found | "
        f"budget allows {can_search} profile search(es) today"
        + (f" | {skipped} deferred to future runs" if skipped else "")
    )

    company_profiles: dict[str, list[dict]] = {}

    for job in new_jobs[:can_search]:
        co = job["company_name"]
        print(f"    → {co}  (match {job['match_score']:.0%})")
        profiles = find_profiles_for_company(co, job["match_score"])
        if profiles:
            company_profiles[co] = profiles
            print(f"       {len(profiles)} profile(s) found")
        else:
            print(f"       No profiles found")

    return company_profiles
