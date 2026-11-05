# Investor co-holding network (SEC Form 13F)

Graph Analytics project, Albert School x Mines, 2026.
Authors: Izan Gael Rooke Mora, Oussama Maaref and Ryan Ebanda.

**The idea:** official sectors group companies by what they do (tech, banks, energy). But investors may group stocks differently. If the same investors tend to buy the same stocks, those stocks may behave as a group, whatever their sector. If those investors sell, the stocks could fall together.

**Our question:** do the groups formed by shared investors differ from official sectors, last over time, and predict which stocks move together better than sectors do?

**Status (5 Nov 2026):** data pipeline and graph design are done and tested; the final graph, centralities, communities and the persistence and returns tests are still to come. This README describes what exists today and will be completed with the analysis.

## Data and sources
- **SEC Form 13F data sets**, 19 quarterly releases covering the report periods 31 Dec 2021 to 30 Jun 2026: https://www.sec.gov/dera/data/form-13f (field definitions: https://www.sec.gov/files/form_13f_readme.pdf). The SEC publishes an accuracy disclaimer and no licence; terms of reuse have not been verified yet.
- **Sector mapping:** OpenFIGI (CUSIP to ticker and security type), SEC `company_tickers.json`, the SEC CIK lookup file and SEC submissions API (company to SIC), and Kenneth French's Fama-French industry definitions. Full list with URLs in [docs/SOURCES.md](docs/SOURCES.md).
- **Code reuse:** no code for these data sets was copied from the internet or from existing projects. The code was written for this project with AI assistance, see [docs/AI_USE.md](docs/AI_USE.md). Methods are cited in SOURCES.md.
- **Raw and processed data are not in the repository** (about 1.4 GB of ZIP files and 0.85 GB of processed files). The scripts below download and rebuild them. The reviewed list of company matches, `data/manual_overrides.csv`, is included.

## How to reproduce
Python 3.11. Install the packages, then set a contact address, which the SEC requires in the User-Agent of automated requests (use your own, never commit it):

```powershell
pip install -r requirements.txt
$env:SEC_CONTACT = "you@example.com"
```

Run from the project folder, in this order. Times are measured on one laptop.

| Step | Command | What it does | Time |
|---|---|---|---|
| 1 | `python src/s01_download_13f.py` | Downloads the 19 releases, keeps long share positions, fixes unit errors | about 10 min after the download |
| 2 | `python src/s01b_flag_inflated.py` | Corrects wrong prices (repeated until stable) and flags unreliable filers | about 8 min |
| 3 | `python src/s02_map_sectors.py` | Maps stocks to company, SIC, Fama-French sector and fund flag | about 3 min with the cached lookups; a first run needs about 30 min of OpenFIGI and SEC lookups |
| 4 | `python src/s03a_null_test.py` | Tests the chance model for shared holders on 2026 Q2 | about 12 min |
| 5 | `python src/s03b_tail_probe.py` | Simulation check of the model and comparison of backbone rules | about 20 min |

Optional: `python src/s02b_name_candidates.py` proposes company matches from the SEC name file (needs `data/raw/sec/cik-lookup-data.txt` from https://www.sec.gov/Archives/edgar/cik-lookup-data.txt). Notebooks in `notebooks/` explore the data (01 managers, 02 stocks) and need the steps above first. Figures go to `figures/`, tables to `results/`.

## Method in brief
- **Graph model:** a bipartite graph of managers and stocks (an edge means the manager held the stock at quarter end), projected onto stocks. One stock is one issuer, identified by the first six CUSIP characters, which merges share classes. The universe is the 1,000 largest operating companies by reported value each quarter.
- **Chance model:** two stocks are linked only if they share more managers than expected by chance given each stock's popularity and each manager's portfolio size (a bipartite configuration model, `src/gutils.py`). On 2026 Q2 it brings the median ratio of observed to expected shared holders from 4.7 to 0.99.
- **Backbone:** each stock keeps its strongest partners (top-k with z above 3); a global threshold either leaves a hairball or an empty graph.

## Layout
- `src/` pipeline scripts, shared helpers in `gutils.py`, settings in `config.py`
- `src/exploration/` one-off diagnostics used to find and check data problems
- `src/drafts/` older scripts, never run and not part of the pipeline
- `feasibility/` the topic-selection tests, including the rejected World Bank topic
- `notebooks/`, `figures/`, `results/`, `docs/` (sources, AI use, project status)

## Known limitations
- Value fixes use thresholds (5x, 2x, 20%) that were not tuned; a few flagged managers may be false alarms.
- No outside check of quarterly totals against published market values.
- Long positions of large US-reporting managers only, as of quarter end and published with a delay of up to 45 days.
- No automated tests; the evidence for reliability is that the pipeline runs end to end from the raw files and reproduces earlier results.
