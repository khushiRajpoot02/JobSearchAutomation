# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

A daily Python automation that scrapes Flutter developer job openings in India, logs them to Google Sheets, finds LinkedIn profiles for networking, and drafts AI-powered referral messages using Google Gemini. Runs on a cron schedule via GitHub Actions at 08:00 AM IST.

## Running the Script

```bash
# Local run (from repo root)
python -m src.main

# Install dependencies
pip install -r requirements.txt
```

There is no build step, test suite, or Makefile. The GitHub Actions workflow runs `python main.py` from within the `src/` directory.

## Environment Setup

Copy `.env.example` to `.env` for local runs. GitHub Actions uses repository secrets:
- `SERPAPI_KEY` — Job/profile searches (250 free credits/month)
- `GEMINI_API_KEY` — Referral message generation
- `GOOGLE_SHEET_ID` — Target Google Spreadsheet ID
- `GOOGLE_CREDENTIALS_JSON` — Google Service Account JSON (entire file contents)

## Architecture

The pipeline is a linear 6-step orchestration in `src/main.py`:

1. Connect to Google Sheets → validate/create "Job Openings" and "Connections" sheets
2. Load existing companies from Connections sheet (for deduplication)
3. Scrape jobs from 3 sources: Google Jobs (SerpAPI), WellFound, Hirist
4. Write new jobs to Job Openings sheet with match scores
5. Find LinkedIn profiles for new companies via SerpAPI Google Search
6. Draft referral messages via Gemini for accepted connections lacking a draft

### Module Responsibilities

| Module | Role |
|--------|------|
| `src/config.py` | All constants: search terms, skill weights, location preferences, sheet schema, API keys |
| `src/main.py` | Orchestrator — runs the 6-step pipeline |
| `src/job_scraper.py` | Aggregates jobs from SerpAPI, WellFound, Hirist; deduplicates and scores |
| `src/profile_finder.py` | Finds HR/recruiter + developer LinkedIn profiles; manages SerpAPI budget |
| `src/sheets_manager.py` | Stateless Google Sheets CRUD; auto-creates sheets with headers if missing |
| `src/message_drafter.py` | Generates personalized referral messages using Gemini; falls back to template |

### Job Match Scoring

Defined in `src/config.py`. Scores 0–100% based on keyword presence in job title/description:
- **Primary skills** (70% weight): flutter, dart, firebase, bloc, getx, riverpod, provider, mobile, ios, android, flutterflow
- **Secondary skills** (30% weight): react, java, github actions, rest api, graphql, ai, auth0, shorebird

### SerpAPI Budget Management

`profile_finder.py` dynamically computes how many profile searches to run per day based on remaining monthly credits and days left in the month — ensuring credits last the whole month. One query per company combines HR and developer keywords.

### Sheet Schema

**Job Openings**: Company, Title, Location, Job Type, YOE, Link, Applied, HR Contact, Match Score, Company Type, Source, Date Found

**Connections**: Connection Name, Profile Link, Company, Their Role, Connection Status, Referral Request Sent, Referral Received, Date Added, Message Draft

## GitHub Actions Workflow

`.github/workflows/daily_job_search.yml` — triggers daily at `30 2 * * *` UTC (08:00 AM IST) and supports manual dispatch. Uses Python 3.11.
