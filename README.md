# Job Search Automation

A daily automation that scrapes developer job openings, logs them to Google Sheets, finds LinkedIn profiles for networking, and drafts AI-powered referral request messages — all running for free on GitHub Actions.

**What it does every morning:**
1. Searches Google Jobs, WellFound, and Hirist for roles matching your skills
2. Scores and filters jobs by location, job type, and skill match
3. Writes new jobs to a Google Sheet with match scores
4. Finds LinkedIn profiles (HR + developers) at companies with open roles
5. Drafts personalized referral messages via Google Gemini for accepted connections

---

## Prerequisites

- A GitHub account (free)
- A Google account (for Sheets + Cloud Console)
- Python 3.11+ (for local testing only)

---

## Step 1 — Get Your API Keys

You need four credentials. All have free tiers sufficient for daily use.

### SerpAPI (job + LinkedIn profile search)
1. Sign up at [serpapi.com](https://serpapi.com) — free plan gives 250 searches/month
2. Copy your API key from the dashboard

### Google Gemini (referral message generation)
1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Create an API key — free tier is more than enough

### Google Sheets + Service Account
1. Create a new Google Spreadsheet — note its ID from the URL:
   `https://docs.google.com/spreadsheets/d/**<SHEET_ID>**/edit`
2. Go to [Google Cloud Console](https://console.cloud.google.com)
3. Create a new project (or use an existing one)
4. Enable the **Google Sheets API** and **Google Drive API** for that project
5. Go to **IAM & Admin → Service Accounts → Create Service Account**
6. Give it any name, click through to finish
7. Click the service account → **Keys → Add Key → JSON** → download the file
8. Open the downloaded JSON file and copy its **entire contents** (you'll need this as a single-line string for the secret)
9. Back in your Google Sheet, click **Share** and add the service account email (it looks like `name@project.iam.gserviceaccount.com`) with **Editor** access

---

## Step 2 — Fork & Customize

### 2a. Fork this repository

Click **Fork** on GitHub. All further changes happen in your fork.

### 2b. Update `src/config.py`

This is the main file you need to edit. Open [src/config.py](src/config.py) and change the following sections:

#### Skills

Replace the skills lists with your own stack. Skills are matched case-insensitively against job titles and descriptions.

```python
# Example for a React Native developer
PRIMARY_SKILLS = [
    "react native", "javascript", "typescript", "ios", "android",
    "mobile", "redux", "expo", "react navigation", "hooks",
]

SECONDARY_SKILLS = [
    "react", "graphql", "rest api", "firebase", "jest",
    "push notification", "deep linking", "in-app purchase",
    "context api", "zustand",
]
```

Primary skills carry **70% weight** in the match score; secondary skills carry **30%**.

#### Search terms

```python
# Example for a React Native developer
SEARCH_TERMS = [
    "Senior React Native Developer",
    "React Native Developer",
    "React Native Engineer",
    "React Native",
]
```

#### Locations

List your preferred cities in order of preference. Jobs in cities not on this list are automatically filtered out. Remote jobs are always included.

```python
LOCATIONS = [
    "Bengaluru",
    "Hyderabad",
    "Noida",
    "Gurgaon",
    "Pune",
    "Mumbai",
]
```

#### Experience range

Set the YOE (years of experience) window you want to target. Jobs outside this range are filtered out.

```python
# Example: 3 years of experience — target roles asking for 1–6 years
YOE_MIN_ACCEPTABLE = 1
YOE_MAX_ACCEPTABLE = 6
```

### 2c. Update `src/message_drafter.py`

The Gemini prompt contains a hardcoded candidate bio. Replace the profile details inside `draft_referral_message()` with your own background.

Find this block (around line 56) and update it:

```python
prompt = f"""You are helping {CANDIDATE_NAME}, a Senior React Native Developer with {YEARS_OF_EXPERIENCE} years of experience, draft a LinkedIn message to request a referral.

About {CANDIDATE_NAME}:
- {YEARS_OF_EXPERIENCE} years of React Native / JavaScript / TypeScript experience
- Built cross-platform apps (Android + iOS) for [your client/domain context]
- Domains: [e.g. fintech, e-commerce, healthcare]
- [Your education] graduate
- Currently a React Native Developer at [Your Company], [City]
- LinkedIn: {CANDIDATE_LINKEDIN}
...
```

Also update the `_fallback_message()` function (used when Gemini is unavailable) — it has hardcoded text specific to the original author around line 110. Replace it with a template that reflects your own background.

---

## Step 3 — Set Up GitHub Actions Secrets

In your forked repository, go to **Settings → Secrets and variables → Actions → New repository secret** and add each of these:

| Secret name | Value |
|---|---|
| `SERPAPI_KEY` | Your SerpAPI key |
| `GEMINI_API_KEY` | Your Gemini API key |
| `GOOGLE_SHEET_ID` | The ID from your spreadsheet URL |
| `GOOGLE_CREDENTIALS_JSON` | The entire contents of the service account JSON file, minified to a single line |
| `CANDIDATE_NAME` | Your full name (e.g. `Jane Smith`) |
| `CANDIDATE_LINKEDIN` | Your LinkedIn URL (e.g. `linkedin.com/in/janesmith`) |
| `YEARS_OF_EXPERIENCE` | A number (e.g. `3`) |

### How to minify the service account JSON to one line

On macOS/Linux:
```bash
cat your-service-account-key.json | python3 -m json.tool --compact
```

Copy the output and paste it as the value for `GOOGLE_CREDENTIALS_JSON`.

### Add the new secrets to the workflow

Open [.github/workflows/daily_job_search.yml](.github/workflows/daily_job_search.yml) and add the three new secrets to the `env:` block of the **Run job search automation** step:

```yaml
- name: Run job search automation
  env:
    SERPAPI_KEY:             ${{ secrets.SERPAPI_KEY }}
    GEMINI_API_KEY:          ${{ secrets.GEMINI_API_KEY }}
    GOOGLE_SHEET_ID:         ${{ secrets.GOOGLE_SHEET_ID }}
    GOOGLE_CREDENTIALS_JSON: ${{ secrets.GOOGLE_CREDENTIALS_JSON }}
    CANDIDATE_NAME:          ${{ secrets.CANDIDATE_NAME }}
    CANDIDATE_LINKEDIN:      ${{ secrets.CANDIDATE_LINKEDIN }}
    YEARS_OF_EXPERIENCE:     ${{ secrets.YEARS_OF_EXPERIENCE }}
  run: |
    cd src
    python main.py
```

---

## Step 4 — Set Your Preferred Run Time

The workflow runs at **08:00 AM IST** by default. To change it, edit the cron line in [.github/workflows/daily_job_search.yml](.github/workflows/daily_job_search.yml):

```yaml
- cron: '30 2 * * *'   # 08:00 AM IST — change this
```

Use [crontab.guru](https://crontab.guru) to generate the right cron expression for your timezone.

---

## Step 5 — Test It Locally (Optional)

```bash
# Clone your fork
git clone https://github.com/your-username/JobSearchAutomation
cd JobSearchAutomation

# Install dependencies
pip install -r requirements.txt

# Set up your .env file
cp .env.example .env
# Edit .env with your actual values

# Run the pipeline
python -m src.main
```

---

## Step 6 — Trigger a Manual Run

Once secrets are set up, go to **Actions → Daily Job Search Automation → Run workflow** to trigger a test run before waiting for the scheduled time.

---

## Using the Google Sheet

The automation writes to two sheets:

**Job Openings** — new jobs appear here daily. Columns:
- `Applied` and `Interested` — fill these in manually (`Yes` / `No`)
- Setting `Interested = Yes` tells the script to search for LinkedIn profiles at that company on the next run

**Connections** — LinkedIn profiles found for companies you marked interested. Columns:
- `Connection Status` — update to `Accepted` once they accept your connection request
- Once `Accepted`, the next run drafts a referral message in the `Message Draft` column
- Review and edit the draft before sending

---

## Customization Reference: React Native Developer Example

Here is a complete diff of what a React Native developer with 3 years of experience would change from the default config:

**`src/config.py`:**

```python
PRIMARY_SKILLS = [
    "react native", "javascript", "typescript", "ios", "android",
    "mobile", "redux", "expo", "react navigation", "hooks",
]

SECONDARY_SKILLS = [
    "react", "graphql", "rest api", "firebase", "jest",
    "push notification", "deep linking", "in-app purchase",
    "context api", "zustand",
]

SEARCH_TERMS = [
    "Senior React Native Developer",
    "React Native Developer",
    "React Native Engineer",
    "React Native",
]

YOE_MIN_ACCEPTABLE = 1
YOE_MAX_ACCEPTABLE = 6
```

**`src/message_drafter.py`** — update the candidate bio in the Gemini prompt and the fallback template to reflect your own background, current company, and education.

**GitHub Secrets** — add all seven secrets listed in Step 3, including `CANDIDATE_NAME`, `CANDIDATE_LINKEDIN`, and `YEARS_OF_EXPERIENCE`.

**`.github/workflows/daily_job_search.yml`** — add the three candidate secrets to the `env:` block as shown in Step 3.

---

## Cost & Limits

| Service | Free tier | Usage per day |
|---|---|---|
| SerpAPI | 250 searches/month | ~10–15 searches |
| Google Gemini | Very generous free tier | ~5–20 messages |
| Google Sheets API | Unlimited (reasonable use) | Minimal |
| GitHub Actions | 2,000 min/month (public repos: unlimited) | ~2–3 min/run |

The script dynamically manages SerpAPI usage to stay within the monthly budget regardless of when you start.
