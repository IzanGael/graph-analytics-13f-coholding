"""Shared paths and parameters. Every analysis choice that affects results is set here."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"

# Quarter label -> (report period in the filings, SEC release that first contains it)
QUARTERS = {
    "2024Q2": ("30-JUN-2024", "01jun2024-31aug2024"),
    "2024Q3": ("30-SEP-2024", "01sep2024-30nov2024"),
    "2024Q4": ("31-DEC-2024", "01dec2024-28feb2025"),
    "2025Q1": ("31-MAR-2025", "01mar2025-31may2025"),
    "2025Q2": ("30-JUN-2025", "01jun2025-31aug2025"),
    "2025Q3": ("30-SEP-2025", "01sep2025-30nov2025"),
    "2025Q4": ("31-DEC-2025", "01dec2025-28feb2026"),
    "2026Q1": ("31-MAR-2026", "01mar2026-31may2026"),
    "2026Q2": ("30-JUN-2026", "01jun2026-31aug2026"),
}
MAIN_QUARTER = "2026Q2"

N_ISSUERS = 1000          # operating companies ranked by total reported value
SEED = 42


def sec_headers():
    """SEC rejects automated requests that do not declare a contact in the User-Agent."""
    contact = os.environ.get("SEC_CONTACT")
    if not contact:
        raise SystemExit("Set the SEC_CONTACT environment variable to your email address first.")
    return {"User-Agent": f"GraphAnalyticsCoursework {contact}"}
