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
CANDIDATE_NAME       = "Arpit Batra"
CANDIDATE_LINKEDIN   = "linkedin.com/in/arpit-batra2"
YEARS_OF_EXPERIENCE  = 5

# Skills drawn directly from the resume — order matters for scoring
PRIMARY_SKILLS = [
    "flutter", "dart", "flutterflow", "cross-platform",
    "ios", "android", "mobile", "bloc", "getx", "provider",
    "firebase", "riverpod",
]

SECONDARY_SKILLS = [
    "react", "java", "github actions", "rest api", "graphql",
    "ai", "shorebird", "firebase analytics", "auth0",
    "deep linking", "in-app purchase", "push notification",
]

# ---------------------------------------------------------------------------
# Job search parameters
# ---------------------------------------------------------------------------
SEARCH_TERMS = [
    "Senior Flutter Developer",
    "Flutter Developer",
    "Flutter Engineer",
    "Flutter"
]

# Locations in preference order (index 0 = most preferred)
LOCATIONS = [
    "Bangalore",
    "Hyderabad",
    "Noida",
    "Gurgaon",
    "Pune",
    "Mumbai",
]
LOCATION_PRIORITY: dict[str, int] = {loc: idx for idx, loc in enumerate(LOCATIONS)}
REMOTE_PRIORITY = len(LOCATIONS)          # Remote comes after all cities

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

# Experience window  (jobs outside this range are filtered out)
YOE_MIN_ACCEPTABLE = 3
YOE_MAX_ACCEPTABLE = 9

# Company filters
MIN_COMPANY_SIZE        = 200   # employees (used in profile-count heuristic)
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
