"""Probe the candidate identifier sources for the sector mapping on known failures from the first test."""
import json
import os
import urllib.request

UA = {"User-Agent": f"GraphAnalyticsCoursework {os.environ['SEC_CONTACT']}", "Content-Type": "application/json"}
# Exxon, Berkshire B, ASML, FedEx, SPY, Apple
CUSIPS = ["30231G102", "084670702", "N07059210", "31428X106", "78462F103", "037833100"]
jobs = [{"idType": "ID_CUSIP", "idValue": c, "exchCode": "US"} for c in CUSIPS]
req = urllib.request.Request("https://api.openfigi.com/v3/mapping", data=json.dumps(jobs).encode(),
                             headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=60) as resp:
    print("rate headers:", {k: v for k, v in resp.headers.items() if "ratelimit" in k.lower()})
    out = json.load(resp)
for cusip, res in zip(CUSIPS, out):
    first = (res.get("data") or [{}])[0]
    print(cusip, {k: first.get(k) for k in ("ticker", "name", "securityType", "securityType2", "marketSector", "exchCode")}, res.get("warning"))

req = urllib.request.Request("https://data.sec.gov/submissions/CIK0000034088.json", headers=UA)
with urllib.request.urlopen(req, timeout=60) as resp:
    d = json.load(resp)
print({k: d.get(k) for k in ("cik", "name", "sic", "sicDescription", "tickers", "entityType")})
