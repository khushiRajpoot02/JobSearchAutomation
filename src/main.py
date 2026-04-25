"""
Job Search Automation — orchestrator.

Modes (pass via --mode):
  find_jobs       Scrape new jobs and write them to the Job Openings sheet.
                  This is the mode used by the daily scheduled run.

  find_profiles   Read all jobs marked Interested=Yes from the sheet and
                  search LinkedIn profiles for companies not yet in Connections.
                  Run this manually after marking jobs as interested.

  draft_messages  Draft referral messages via Gemini for every connection
                  whose status is Accepted but has no message yet.
                  Run this manually after a connection request is accepted.
"""

import argparse
import sys
import traceback
from datetime import datetime

from config import JOBS_SHEET_NAME, CONNECTIONS_SHEET_NAME
from job_scraper import get_all_jobs
from sheets_manager import (
    get_client,
    open_sheets,
    add_jobs,
    add_connections,
    get_interested_companies,
    get_interested_jobs_from_sheet,
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
# Mode: find_jobs
# ---------------------------------------------------------------------------

def run_find_jobs(jobs_ws, conns_ws) -> dict:
    _header("Step 1 / 2 — Scraping new job openings")
    jobs = get_all_jobs()

    _header("Step 2 / 2 — Updating Job Openings sheet")
    try:
        jobs_added = add_jobs(jobs_ws, jobs)
        _ok(f"{jobs_added} new job(s) added  |  {len(jobs) - jobs_added} duplicate(s) skipped")
    except Exception as exc:
        _fail(f"Failed to update Jobs sheet: {exc}")
        jobs_added = 0

    return {"jobs_added": jobs_added}


# ---------------------------------------------------------------------------
# Mode: find_profiles
# ---------------------------------------------------------------------------

def run_find_profiles(jobs_ws, conns_ws) -> dict:
    _header("Step 1 / 2 — Loading interested companies from sheet")
    try:
        existing_companies = get_existing_companies_in_connections(conns_ws)
        _ok(f"{len(existing_companies)} company(s) already tracked in Connections")
    except Exception as exc:
        _warn(f"Could not load existing companies: {exc}")
        existing_companies = set()

    try:
        interested_jobs = get_interested_jobs_from_sheet(jobs_ws)
        interested_companies = {j["company_name"] for j in interested_jobs}
        _ok(f"{len(interested_jobs)} job(s) marked as Interested")
    except Exception as exc:
        _fail(f"Could not load interested jobs from sheet: {exc}")
        return {"profiles_added": 0}

    if not interested_jobs:
        _ok("No jobs marked Interested — nothing to do")
        _ok(f"Tip: set 'Interested' → 'Yes' in the '{JOBS_SHEET_NAME}' sheet and re-run")
        return {"profiles_added": 0}

    new_jobs = [j for j in interested_jobs if j["company_name"] not in existing_companies]
    if not new_jobs:
        _ok("All interested companies are already tracked in the Connections sheet")
        return {"profiles_added": 0}

    _header("Step 2 / 2 — Searching LinkedIn profiles")
    total_profiles_added = 0
    try:
        company_profiles = find_profiles_for_new_jobs(new_jobs, existing_companies)
        if company_profiles:
            all_profiles = [p for profiles in company_profiles.values() for p in profiles]
            total_profiles_added = add_connections(conns_ws, all_profiles)
            _ok(
                f"{total_profiles_added} profile(s) added across "
                f"{len(company_profiles)} company(s)"
            )
        else:
            _ok("No new profiles found")
    except Exception as exc:
        _warn(f"Profile search failed: {exc}")

    return {"profiles_added": total_profiles_added}


# ---------------------------------------------------------------------------
# Mode: draft_messages
# ---------------------------------------------------------------------------

def run_draft_messages(conns_ws) -> dict:
    _header("Finding accepted connections that need a message draft")
    try:
        accepted = get_accepted_connections_needing_message(conns_ws)
    except Exception as exc:
        _fail(f"Could not read Connections sheet: {exc}")
        return {"messages_drafted": 0}

    if not accepted:
        _ok("No accepted connections needing messages right now")
        return {"messages_drafted": 0}

    _ok(f"{len(accepted)} accepted connection(s) to draft")
    drafted = 0
    for conn in accepted:
        name = conn.get("Connection Name", "Unknown")
        print(f"\n    Drafting for {name} @ {conn.get('Company Name', '?')} …")
        try:
            message = draft_referral_message(conn)
            update_message_draft(conns_ws, conn["_row_index"], message)
            _ok(f"Message saved for {name}")
            drafted += 1
        except Exception as exc:
            _warn(f"Could not draft message for {name}: {exc}")

    return {"messages_drafted": drafted}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Job Search Automation")
    parser.add_argument(
        "--mode",
        choices=["find_jobs", "find_profiles", "draft_messages"],
        default="find_jobs",
        help="Which part of the pipeline to run",
    )
    args = parser.parse_args()

    start_time = datetime.now()
    print(f"\n{'═' * 60}")
    print(f"  Job Search Automation  —  {start_time.strftime('%A, %d %b %Y  %H:%M')}")
    print(f"  Mode: {args.mode}")
    print(f"{'═' * 60}")

    _header("Connecting to Google Sheets")
    try:
        client = get_client()
        jobs_ws, conns_ws = open_sheets(client)
        _ok("Connected  |  Sheets ready")
    except Exception as exc:
        _fail(f"Could not connect to Google Sheets: {exc}")
        print("\n  Full traceback:")
        traceback.print_exc()
        sys.exit(1)

    if args.mode == "find_jobs":
        stats = run_find_jobs(jobs_ws, conns_ws)
    elif args.mode == "find_profiles":
        stats = run_find_profiles(jobs_ws, conns_ws)
    elif args.mode == "draft_messages":
        stats = run_draft_messages(conns_ws)

    elapsed = (datetime.now() - start_time).seconds
    print(f"\n{'═' * 60}")
    print("  ✅  Run complete!")
    print(f"{'═' * 60}")
    for key, val in stats.items():
        label = key.replace("_", " ").capitalize()
        print(f"  • {label:<28}: {val}")
    print(f"  • {'Time taken':<28}: {elapsed}s")

    if args.mode == "find_jobs":
        print(f"\n  ℹ  Next step: open the '{JOBS_SHEET_NAME}' sheet,")
        print(f"     review new jobs, and mark 'Interested' → 'Yes'.")
        print(f"     Then trigger the 'Find LinkedIn Profiles' workflow.")
    elif args.mode == "find_profiles":
        print(f"\n  ℹ  Next step: send connection requests on LinkedIn,")
        print(f"     then update 'Connection Status' → 'Pending' in the sheet.")
        print(f"     When a request is accepted, trigger the 'Draft Messages' workflow.")
    elif args.mode == "draft_messages":
        print(f"\n  ℹ  Next step: review the drafts in the '{CONNECTIONS_SHEET_NAME}' sheet")
        print(f"     and send the edited message on LinkedIn.")
    print()


if __name__ == "__main__":
    main()
