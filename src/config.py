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
    "2021Q4": ("31-DEC-2021", "2022q1"),
    "2022Q1": ("31-MAR-2022", "2022q2"),
    "2022Q2": ("30-JUN-2022", "2022q3"),
    "2022Q3": ("30-SEP-2022", "2022q4"),
    "2022Q4": ("31-DEC-2022", "2023q1"),
    "2023Q1": ("31-MAR-2023", "2023q2"),
    "2023Q2": ("30-JUN-2023", "2023q3"),
    "2023Q3": ("30-SEP-2023", "2023q4"),
    "2023Q4": ("31-DEC-2023", "01jan2024-29feb2024"),
    "2024Q1": ("31-MAR-2024", "01mar2024-31may2024"),
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

# Provisional until checked against results/sensitivity.csv
RECIPE = dict(low=10, high=200, method="knn", top_k=15, z_min=3.0)
LOUVAIN_RUNS = 20


def sec_headers():
    """SEC rejects automated requests that do not declare a contact in the User-Agent."""
    contact = os.environ.get("SEC_CONTACT")
    if not contact:
        raise SystemExit("Set the SEC_CONTACT environment variable to your email address first.")
    return {"User-Agent": f"GraphAnalyticsCoursework {contact}"}
