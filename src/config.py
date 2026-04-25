"""
Central configuration for Job Search Automation.
All tuneable parameters live here — no need to touch other files for basic customisation.
"""

import os

# ---------------------------------------------------------------------------
# Secrets  (injected via GitHub Actions Secrets / local .env)
# ---------------------------------------------------------------------------
SERPAPI_KEY            = os.environ.get("SERPAPI_KEY", "")
GEMINI_API_KEY         = os.environ.get("GEMINI_API_KEY", "")
GOOGLE_SHEET_ID        = os.environ.get("GOOGLE_SHEET_ID", "")
# Full service-account JSON stored as a single-line string in the secret
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")

# ---------------------------------------------------------------------------
# Candidate profile  (used to score job matches & personalise messages)
# ---------------------------------------------------------------------------
CANDIDATE_NAME       = os.environ.get("CANDIDATE_NAME", "")
CANDIDATE_LINKEDIN   = os.environ.get("CANDIDATE_LINKEDIN", "")
YEARS_OF_EXPERIENCE  = int(os.environ.get("YEARS_OF_EXPERIENCE", "0"))

# Skills drawn directly from the resume — order matters for scoring
PRIMARY_SKILLS = [
    "React Native", "JavaScript", "cross-platform",
    "ios", "android", "mobile", "redux", "redux-toolkit", "provider",
    "firebase", "Mobile Application Development", 
]

SECONDARY_SKILLS = [
    "React.js", "java", "github actions", "rest api", "graphql",
    "ai", "firebase analytics", "auth0",
    "deep linking", "in-app purchase", "push notification",
]

# ---------------------------------------------------------------------------
# Job search parameters
# ---------------------------------------------------------------------------
SEARCH_TERMS = [
    "React Native Developer",
     "React Native",
 
]

# Locations in preference order (index 0 = most preferred).
# Only jobs from these cities (or remote) are shown; all others are hard-filtered.
LOCATIONS = [
    "Bengaluru",
    "Hyderabad",
    "Noida",
    "Gurgaon",
    "Pune",
    "Mumbai",
    "Chandigarh",
]
LOCATION_PRIORITY: dict[str, int] = {loc: idx for idx, loc in enumerate(LOCATIONS)}
REMOTE_PRIORITY = len(LOCATIONS)          # Remote comes after all cities

# Common spelling/naming aliases → canonical LOCATIONS name
LOCATION_ALIASES: dict[str, str] = {
    "bangalore":  "Bengaluru",
    "bengaluru":  "Bengaluru",
    "gurugram":   "Gurgaon",
    "gurgaon":    "Gurgaon",
}

SKIP_LOCATION_SCORE = 998   # Sentinel — job is in a non-preferred city, discard

# Job-type priority  (lower = more preferred)
JOB_TYPE_PRIORITY: dict[str, int] = {
    "hybrid":           0,
    "remote":           1,
    "work from home":   1,
    "wfh":              1,
    "on-site":          2,
    "onsite":           2,
    "work from office": 2,
    "wfo":              2,
    "in-office":        2,
}
SKIP_JOB_TYPE_SCORE = 999   # Sentinel — job will be discarded

# Source platform priority (lower = more preferred).
# Google Jobs results carry per-listing source info extracted from apply_options.
SOURCE_PRIORITY: dict[str, int] = {
    "linkedin":  0,
    "naukri":    1,
    "instahyre": 2,
    "hirist":    3,
    "indeed":    4,
    "wellfound": 5,
    "angellist": 5,   # WellFound legacy domain
}

# SerpAPI pagination — each page costs 1 credit (10 results/page)
GOOGLE_JOBS_PAGES = 3

# Experience window  (jobs outside this range are filtered out)
YOE_MIN_ACCEPTABLE = 2
YOE_MAX_ACCEPTABLE = 5

# Company filters
MIN_COMPANY_SIZE        = 25   # employees (used in profile-count heuristic)
PREFER_PRODUCT_COMPANY  = True

# ---------------------------------------------------------------------------
# Profile-suggestion logic
# ---------------------------------------------------------------------------
def get_suggested_profile_count(match_score: float) -> int:
    """
    Returns how many LinkedIn profiles to surface for a company.
    Purely based on job-match quality; company-size data isn't reliably
    available without a paid API, so we keep it simple.

      match_score 0.8-1.0  → 6 profiles
      match_score 0.5-0.8  → 4 profiles
      match_score 0.2-0.5  → 2 profiles
    """
    if match_score >= 0.8:
        return 6
    if match_score >= 0.5:
        return 4
    return 2

# ---------------------------------------------------------------------------
# Sheet names
# ---------------------------------------------------------------------------
JOBS_SHEET_NAME        = "Job Openings"
CONNECTIONS_SHEET_NAME = "Connections"

# Column headers — order defines column positions in the sheet
JOB_COLUMNS = [
    "Company Name",
    "Job Title",
    "Location",
    "Job Type",           # Hybrid / Remote / On-site
    "YOE Required",
    "Job Link",
    "Applied",            # No / Yes
    "Interested",         # No / Yes — manually set; gates profile search
    "HR Contact",
    "Match Score",
    "Company Type",       # Product / Service / Unknown
    "Source",
    "Date Found",
]

CONNECTION_COLUMNS = [
    "Connection Name",
    "Profile Link",
    "Company Name",
    "Their Role",
    "Connection Status",        # Not Sent / Pending / Accepted / Declined
    "Referral Request Sent",    # No / Yes
    "Referral Received",        # No / Yes
    "Date Added",
    "Message Draft",
]
