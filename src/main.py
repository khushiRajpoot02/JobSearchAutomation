"""
Job Search Automation — daily orchestrator.

Run order:
  1. Connect to Google Sheets (create sheets if needed)
  2. Scrape new jobs from all sources
  3. Add new jobs to Sheet 1 ("Job Openings")
  4. Find LinkedIn profiles for NEW companies (not already tracked)
  5. Add those profiles to Sheet 2 ("Connections") — status: "Not Sent"
     → You manually send the requests on LinkedIn and flip status → "Pending"
  6. Draft personalised referral messages for connections that became "Accepted"
     (you update the status manually in the sheet after seeing the LinkedIn notification)
  7. Print a summary
"""

import sys
from datetime import datetime

from config import JOBS_SHEET_NAME, CONNECTIONS_SHEET_NAME
from job_scraper import get_all_jobs
from sheets_manager import (
    get_client,
    open_sheets,
    add_jobs,
    add_connections,
    get_interested_companies,
    get_existing_companies_in_connections,
    get_accepted_connections_needing_message,
    update_message_draft,
)
from profile_finder import find_profiles_for_new_jobs
from message_drafter import draft_referral_message


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def _header(text: str):
    width = 60
    print(f"\n{'─' * width}")
    print(f"  {text}")
    print(f"{'─' * width}")


def _ok(text: str):
    print(f"  ✓  {text}")


def _warn(text: str):
    print(f"  ⚠  {text}")


def _fail(text: str):
    print(f"  ✗  {text}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    start_time = datetime.now()
    print(f"\n{'═' * 60}")
    print(f"  Job Search Automation  —  {start_time.strftime('%A, %d %b %Y  %H:%M')}")
    print(f"{'═' * 60}")

    # ── Step 1: Google Sheets ────────────────────────────────────────────────
    _header("Step 1 / 6 — Connecting to Google Sheets")
    try:
        client         = get_client()
        jobs_ws, conns_ws = open_sheets(client)
        _ok("Connected  |  Sheets ready")
    except Exception as exc:
        _fail(f"Could not connect to Google Sheets: {exc}")
        sys.exit(1)

    # ── Step 2: Load interested companies and existing connections ───────────
    _header("Step 2 / 6 — Loading existing connection data")
    try:
        existing_companies = get_existing_companies_in_connections(conns_ws)
        _ok(f"{len(existing_companies)} companies already in Connections sheet")
    except Exception as exc:
        _warn(f"Could not load existing companies: {exc}")
        existing_companies = set()

    try:
        interested_companies = get_interested_companies(jobs_ws)
        _ok(f"{len(interested_companies)} company(s) marked as Interested")
    except Exception as exc:
        _warn(f"Could not load interested companies: {exc}")
        interested_companies = set()

    # ── Step 3: Scrape jobs ──────────────────────────────────────────────────
    _header("Step 3 / 6 — Scraping new job openings")
    jobs = get_all_jobs()

    # ── Step 4: Update Jobs sheet ────────────────────────────────────────────
    _header("Step 4 / 6 — Updating Job Openings sheet")
    try:
        jobs_added = add_jobs(jobs_ws, jobs)
        _ok(f"{jobs_added} new job(s) added  |  {len(jobs) - jobs_added} duplicate(s) skipped")
    except Exception as exc:
        _fail(f"Failed to update Jobs sheet: {exc}")
        jobs_added = 0

    # ── Step 5: Find LinkedIn profiles for interested companies ─────────────
    _header("Step 5 / 6 — Finding LinkedIn profiles for referrals")
    total_profiles_added = 0

    # Only search profiles for companies the user marked Interested = Yes
    # and that aren't already in the Connections sheet.
    interested_jobs = [
        j for j in jobs
        if j.get("company_name") in interested_companies
        and j.get("company_name") not in existing_companies
    ]

    if not interested_companies:
        _ok("No jobs marked as Interested — skipping profile search")
        _ok("Tip: set 'Interested' → 'Yes' in the Job Openings sheet to trigger profile search")
    elif interested_jobs:
        try:
            company_profiles = find_profiles_for_new_jobs(interested_jobs, existing_companies)

            if company_profiles:
                all_new_profiles = [
                    p for profiles in company_profiles.values() for p in profiles
                ]
                total_profiles_added = add_connections(conns_ws, all_new_profiles)
                _ok(
                    f"{total_profiles_added} profile(s) added across "
                    f"{len(company_profiles)} company(s)"
                )
            else:
                _ok("No new profiles found for interested companies")

        except Exception as exc:
            _warn(f"Profile search partially failed: {exc}")
    else:
        _ok("Interested companies are already tracked in the Connections sheet")

    # ── Step 6: Draft messages for accepted connections ──────────────────────
    _header("Step 6 / 6 — Drafting referral messages for accepted connections")
    try:
        accepted = get_accepted_connections_needing_message(conns_ws)

        if accepted:
            _ok(f"{len(accepted)} accepted connection(s) need a message draft")
            for conn in accepted:
                name = conn.get("Connection Name", "Unknown")
                print(f"\n    Drafting for {name} @ {conn.get('Company Name', '?')} …")
                try:
                    message = draft_referral_message(conn)
                    update_message_draft(conns_ws, conn["_row_index"], message)
                    _ok(f"Message saved for {name}")
                except Exception as exc:
                    _warn(f"Could not draft message for {name}: {exc}")
        else:
            _ok("No accepted connections needing messages right now")

    except Exception as exc:
        _warn(f"Message drafting step failed: {exc}")
        accepted = []

    # ── Summary ──────────────────────────────────────────────────────────────
    elapsed = (datetime.now() - start_time).seconds
    print(f"\n{'═' * 60}")
    print("  ✅  Run complete!")
    print(f"{'═' * 60}")
    print(f"  • New jobs added          : {jobs_added}")
    print(f"  • New profiles added      : {total_profiles_added}")
    print(f"  • Messages drafted        : {len(accepted) if isinstance(accepted, list) else 0}")
    print(f"  • Time taken              : {elapsed}s")
    print(f"\n  ℹ  Next steps (manual):")
    print(f"     1. Open the '{CONNECTIONS_SHEET_NAME}' sheet")
    print(f"        — review profiles & send connection requests on LinkedIn")
    print(f"        — update 'Connection Status' → 'Pending' after sending")
    print(f"     2. When a request is accepted on LinkedIn,")
    print(f"        update 'Connection Status' → 'Accepted'")
    print(f"        The next daily run will auto-draft a referral message.")
    print(f"     3. Open the '{JOBS_SHEET_NAME}' sheet")
    print(f"        — mark 'Applied' → 'Yes' after applying")
    print()


if __name__ == "__main__":
    main()
