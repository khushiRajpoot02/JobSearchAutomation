"""
Google Sheets interface.

Sheet 1 — "Job Openings"  : one row per job found
Sheet 2 — "Connections"   : one row per LinkedIn profile surfaced for referral

The module is intentionally stateless — every function receives the worksheet
it needs, so callers control which spreadsheet is open.
"""

import json
from datetime import datetime
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from config import (
    GOOGLE_SHEET_ID,
    GOOGLE_CREDENTIALS_JSON,
    JOBS_SHEET_NAME,
    CONNECTIONS_SHEET_NAME,
    JOB_COLUMNS,
    CONNECTION_COLUMNS,
)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ---------------------------------------------------------------------------
# Colour palette for header rows
# ---------------------------------------------------------------------------
_JOBS_HEADER_COLOR       = {"red": 0.13, "green": 0.37, "blue": 0.64}   # deep blue
_CONNECTIONS_HEADER_COLOR = {"red": 0.18, "green": 0.53, "blue": 0.34}  # deep green


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def get_client() -> gspread.Client:
    """Build and return an authorised gspread client."""
    if not GOOGLE_CREDENTIALS_JSON:
        raise EnvironmentError("GOOGLE_CREDENTIALS_JSON is not set.")
    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    creds      = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
    return gspread.authorize(creds)


def get_or_create_sheet(
    client: gspread.Client,
    sheet_name: str,
    headers: list[str],
    header_color: dict,
) -> gspread.Worksheet:
    """
    Opens the named worksheet inside GOOGLE_SHEET_ID.
    Creates it (with formatted headers) if it doesn't exist yet.
    """
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)

    try:
        ws = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(
            title=sheet_name,
            rows=2000,
            cols=len(headers),
        )

    # Ensure header row is present and correct
    first_row = ws.row_values(1) if ws.row_count >= 1 else []
    if first_row != headers:
        ws.clear()
        ws.append_row(headers, value_input_option="USER_ENTERED")
        ws.format(
            "1:1",
            {
                "backgroundColor": header_color,
                "textFormat": {
                    "bold": True,
                    "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                    "fontSize": 10,
                },
                "horizontalAlignment": "CENTER",
            },
        )
        # Freeze header row so it stays visible while scrolling
        ws.freeze(rows=1)

    return ws


def open_sheets(client: gspread.Client) -> tuple[gspread.Worksheet, gspread.Worksheet]:
    """Convenience wrapper — returns (jobs_sheet, connections_sheet)."""
    jobs_ws = get_or_create_sheet(
        client, JOBS_SHEET_NAME, JOB_COLUMNS, _JOBS_HEADER_COLOR
    )
    conns_ws = get_or_create_sheet(
        client, CONNECTIONS_SHEET_NAME, CONNECTION_COLUMNS, _CONNECTIONS_HEADER_COLOR
    )
    return jobs_ws, conns_ws


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _get_all_as_dicts(ws: gspread.Worksheet) -> list[dict]:
    """Returns all rows (except header) as list of dicts keyed by column header."""
    rows = ws.get_all_values()
    if len(rows) <= 1:
        return []
    headers = rows[0]
    return [dict(zip(headers, row)) for row in rows[1:]]


def _col_index(ws: gspread.Worksheet, col_name: str) -> int:
    """1-based column index for a header name."""
    headers = ws.row_values(1)
    return headers.index(col_name) + 1   # gspread is 1-indexed


# ---------------------------------------------------------------------------
# Jobs sheet operations
# ---------------------------------------------------------------------------

def get_existing_job_links(ws: gspread.Worksheet) -> set[str]:
    rows = _get_all_as_dicts(ws)
    return {r.get("Job Link", "") for r in rows if r.get("Job Link")}


def get_interested_companies(ws: gspread.Worksheet) -> set[str]:
    """
    Returns company names from Job Openings rows where Interested == "Yes".
    Only these companies will have their LinkedIn profiles searched.
    """
    rows = _get_all_as_dicts(ws)
    return {
        r["Company Name"]
        for r in rows
        if r.get("Interested", "").strip().lower() == "yes"
        and r.get("Company Name")
    }


def add_jobs(ws: gspread.Worksheet, jobs: list[dict]) -> int:
    """
    Inserts only NEW jobs (de-duplicated by link).
    Returns the count of rows actually added.
    """
    existing = get_existing_job_links(ws)
    today    = datetime.now().strftime("%Y-%m-%d")

    rows_to_add = []
    for job in jobs:
        if not job.get("link") or job["link"] in existing:
            continue

        rows_to_add.append([
            job.get("company_name", ""),
            job.get("title", ""),
            job.get("location", ""),
            job.get("job_type_label", "Unknown"),
            job.get("yoe", "Not specified"),
            job.get("link", ""),
            "No",                                        # Applied
            "No",                                        # Interested
            job.get("hr_contact", ""),
            f"{job.get('match_score', 0):.0%}",
            "Product" if job.get("is_product_company") else "Service/Unknown",
            job.get("source", ""),
            today,
        ])

    if rows_to_add:
        ws.append_rows(rows_to_add, value_input_option="USER_ENTERED")

    return len(rows_to_add)


# ---------------------------------------------------------------------------
# Connections sheet operations
# ---------------------------------------------------------------------------

def get_existing_profile_links(ws: gspread.Worksheet) -> set[str]:
    rows = _get_all_as_dicts(ws)
    return {r.get("Profile Link", "") for r in rows if r.get("Profile Link")}


def get_existing_companies_in_connections(ws: gspread.Worksheet) -> set[str]:
    rows = _get_all_as_dicts(ws)
    return {r.get("Company Name", "") for r in rows if r.get("Company Name")}


def add_connections(ws: gspread.Worksheet, profiles: list[dict]) -> int:
    """
    Inserts only NEW profiles (de-duplicated by LinkedIn URL).
    Returns the count of rows actually added.
    """
    existing = get_existing_profile_links(ws)
    today    = datetime.now().strftime("%Y-%m-%d")

    rows_to_add = []
    for p in profiles:
        link = p.get("profile_link", "")
        if not link or link in existing:
            continue
        rows_to_add.append([
            p.get("name", ""),
            link,
            p.get("company_name", ""),
            p.get("job_title", ""),
            "Not Sent",   # Connection Status
            "No",         # Referral Request Sent
            "No",         # Referral Received
            today,
            "",           # Message Draft — filled later by message_drafter
        ])

    if rows_to_add:
        ws.append_rows(rows_to_add, value_input_option="USER_ENTERED")

    return len(rows_to_add)


def get_accepted_connections_needing_message(ws: gspread.Worksheet) -> list[dict]:
    """
    Returns rows where:
      • Connection Status  == "Accepted"
      • Referral Request Sent == "No"
      • Message Draft is empty

    Each dict also carries _row_index (1-based, includes header row).
    """
    all_rows = ws.get_all_values()
    if len(all_rows) <= 1:
        return []

    headers = all_rows[0]
    results = []
    for i, row in enumerate(all_rows[1:], start=2):
        d = dict(zip(headers, row))
        if (
            d.get("Connection Status") == "Accepted"
            and d.get("Referral Request Sent", "No") == "No"
            and not d.get("Message Draft", "").strip()
        ):
            d["_row_index"] = i
            results.append(d)

    return results


def update_message_draft(ws: gspread.Worksheet, row_index: int, message: str) -> None:
    col = _col_index(ws, "Message Draft")
    ws.update_cell(row_index, col, message)


def mark_referral_request_sent(ws: gspread.Worksheet, row_index: int) -> None:
    col = _col_index(ws, "Referral Request Sent")
    ws.update_cell(row_index, col, "Yes")


def update_connection_status(ws: gspread.Worksheet, row_index: int, status: str) -> None:
    """status should be one of: Not Sent / Pending / Accepted / Declined"""
    col = _col_index(ws, "Connection Status")
    ws.update_cell(row_index, col, status)
