# Investor co-holding network (SEC Form 13F)

Graph Analytics project, Albert School x Mines, 2026.
Authors: Izan Gael Rooke Mora, Oussama Maaref and Ryan Ebanda.

**The idea:** official sectors group companies by what they do (tech, banks, energy). But investors may group stocks differently. If the same investors tend to buy the same stocks, those stocks may behave as a group, whatever their sector.

**Our question:** do the groups formed by shared investors differ from official sectors, last over time, and predict which stocks move together better than sectors do?

**Status (6 Nov 2026):** the data pipeline and the graphs for all 19 quarters are built and reproducible. Centralities, communities, persistence and the returns test are still to come. The results below are preliminary.

## Data and sources
- **SEC Form 13F data sets**, 19 quarterly releases covering the report periods 31 Dec 2021 to 30 Jun 2026: https://www.sec.gov/dera/data/form-13f (field definitions: https://www.sec.gov/files/form_13f_readme.pdf). The SEC publishes an accuracy disclaimer and no licence; terms of reuse have not been verified yet.
- **Sector mapping:** OpenFIGI (CUSIP to ticker and security type), SEC `company_tickers.json`, the SEC CIK lookup file and the SEC submissions API (company to SIC), and Kenneth French's Fama-French industry definitions. Full list with URLs in [docs/SOURCES.md](docs/SOURCES.md).
- **Code reuse:** no code for these data sets was copied from the internet or from existing projects. The code was written for this project with AI assistance, see [docs/AI_USE.md](docs/AI_USE.md). Methods are cited in SOURCES.md.
- **Raw and processed data are not in the repository** (about 1.4 GB of ZIP files and about 1.8 GB of processed files). The scripts below download and rebuild them. The reviewed list of company matches, `data/manual_overrides.csv`, is included.
- **Processed data, ready to use (zip, about 740 MB):** [direct download link](https://drive.google.com/file/d/1K8UPFQDs8XA4jv1i86lP-VDyOBAldtag/view?usp=sharing) (file `processed_13f_2021Q4-2026Q2.zip`, built 6 Nov 2026), or the [Google Drive folder](https://drive.google.com/drive/folders/1KfR8t2zsmP6KvTb8sfD-eMcY95sI3sG7), file `processed_13f_2021Q4-2026Q2.zip`, with a `MANIFEST.txt` listing the SHA-256 hash of each file. Unzip it into `data/interim/` and skip steps 1 to 3 below. The raw SEC files are public and are not copied there.

## How to reproduce
Python 3.11. Install the packages, then set a contact address, which the SEC requires in the User-Agent of automated requests (use your own, never commit it):

```powershell
pip install -r requirements.txt
$env:SEC_CONTACT = "you@example.com"
```

Run from the project folder, in this order. Times are measured on one laptop.

| Step | Command | What it does | Time |
|---|---|---|---|
| 1 | `python src/s01_download_13f.py` | Downloads the 19 releases, builds each manager's report (corrected filings included), fixes unit errors | about 10 min after the download |
| 2 | `python src/s01b_flag_inflated.py` | Corrects wrong prices (repeated until stable) and flags unreliable filers | about 8 min |
| 3 | `python src/s02_map_sectors.py` | Maps stocks to company, SIC, Fama-French sector and fund flag | about 3 min with the cached lookups; a first run needs about 30 min of OpenFIGI and SEC lookups |
| 4 | `python src/s04_build_graphs.py` | Builds the main graph (top 15 links per stock) and the sensitivity graphs (10 and 25) for all 19 quarters | about 15 min |
| 5 | `python src/s04b_graph_figures.py` | Draws the graph-over-time figure | under 1 min |

Optional diagnostics, rerun on the current data on 6 Nov 2026: `python src/s03a_null_test.py` (chance model check on 2026 Q2, about 12 min), `python src/s03b_tail_probe.py` (simulation check and backbone comparison, about 20 min), `python src/s03c_backbone_figure.py` (figure of the backbone comparison), and `python src/s02b_name_candidates.py` (proposes company matches from the SEC name file; needs `data/raw/sec/cik-lookup-data.txt` from https://www.sec.gov/Archives/edgar/cik-lookup-data.txt).

Tests: `python tests/test_gutils.py` (4 checks on the chance model; they should print "all tests passed").

Notebooks in `notebooks/` explore the data (01 managers, 02 stocks) and need steps 1 to 3 first. Figures go to `figures/`, tables to `results/`.

## Method in brief
- **Filings:** for each manager and quarter, the report is the latest RESTATEMENT amendment if there is one, otherwise the original 13F-HR. NEW HOLDINGS amendments add their positions. Long share positions only; options excluded.
- **Graph model:** a bipartite graph of managers and stocks (an edge means the manager held the stock at quarter end), projected onto stocks. One stock is one issuer, identified by the first six CUSIP characters, which merges share classes. The universe is the 1,000 largest operating companies by reported value each quarter, held by at least 50 managers. Two ExxonMobil listings (CUSIPs 30231G and 30233Q, the 2026 holding-company reorganisation) are counted as one company (`ISSUER_ALIASES` in `config.py`).
- **Chance model:** two stocks are linked only if they share more managers than expected by chance given each stock's popularity and each manager's portfolio size (a bipartite configuration model, `src/gutils.py`).
- **Backbone:** each stock keeps its 15 strongest partners, with z above 3. Sensitivity graphs keep 10 and 25.

## Results (main graph, 2026 Q2)
- 1,000 stocks, 8,226 managers, 10,134 links (about 20 per stock).
- 934 stocks in the biggest connected group, 47 stocks with no link, 54 connected groups in total.
- Across all quarters the graph stays at 9,500 to 10,200 links, and 87% to 93% of stocks are the same as the quarter before.

## Layout
- `src/` pipeline scripts, shared helpers in `gutils.py`, settings in `config.py`
- `src/exploration/` one-off diagnostics used to find and check data problems
- `src/drafts/` old drafts, never run and not part of any result (see `src/drafts/README.md`)
- `src/regimes/` regime tests, conviction graph, graph measures and co-movement test (see the section above)
- `neo4j/` the Neo4j demo used for the oral defense (visualisation only)
- `report/` the written report: LaTeX source on the course template, `biblio.bib`, figures (`make_figures.py`) and the compiled PDF
- `feasibility/` the topic-selection tests, including the rejected World Bank topic
- `notebooks/`, `figures/`, `results/`, `docs/` (sources, AI use, project status)

## Known limitations
- Value fixes use thresholds (5x, 2x, 20%) that were not tuned; a few flagged managers may be false alarms (for example Bank of Montreal).
- No outside check of quarterly totals against published market values.
- Long positions of large US-reporting managers only, as of quarter end and published with a delay of up to 45 days.
- A 13F manager is a filing institution, not a single fund.
- Sector labels are the SEC's industry codes, not each company's business mix (for example Amazon is labelled retail).
- No automated tests beyond the four chance-model checks; the evidence for reliability is that the pipeline runs end to end from the raw files.

## Extension: macro regimes, conviction graph and co-movement (8 Nov 2026)
Scripts in `src/regimes/`, outputs in `results/regimes/`. They need the main graphs (`s04`) first. Run from the project folder, in this order:

| Step | Command | What it does |
|---|---|---|
| A | `python src/regimes/regime_test.py results/graph_summary.csv results/regimes` | Links: do they change more at the 5 macro regime boundaries? |
| B | `python src/regimes/regime_groups.py . results/regimes` | Louvain groups per quarter, 19 x 19 group similarity heatmap, boundary test |
| C | `python src/regimes/investor_calendar.py . results/regimes` then `python src/regimes/calendar_break_test.py results/regimes` | Data-driven "investor calendar" (best cuts vs a smooth-drift baseline) and break strength per quarter |
| D | `python src/regimes/conviction_build.py . results/regimes/conviction` | Conviction graph: stocks linked when the same managers bet on both (relative overweight > 2; checks 1.5 and 3) |
| E | `python src/regimes/conviction_analysis.py . results/regimes` | Same regime tests on the conviction graph; ownership vs conviction, size control |
| F | `python src/regimes/conviction_profiles.py . results/regimes/conviction 2022Q2 2026Q2` | Profiles of the bet groups ("tribes") |
| G | `python src/regimes/graph_metrics.py . results/regimes/metrics 2026Q2` | Components, diameter, radius (largest component, hops), centralities, both graphs |
| H | `python src/regimes/returns_13f.py . results/regimes/comovement` then `python src/regimes/comovement_test.py . results/regimes/comovement` | Quarterly returns from filings (split-adjusted) and the co-movement test |

`src/regimes/conviction_probe.py <repo> <quarter>` prints the checks used to choose the overweight rule. Steps D and E take about 10 and 15 minutes.

**Relative overweight:** a manager's weight in a stock divided by the weight the stock would have if the manager held its own stocks in market proportions. Above 1 the manager made it bigger than the market would; a bet is an overweight above 2.

**Main results (preliminary):**
- Macro regimes (6, defined by the team; dates approximate) do not reorganise the groups: links p = 0.61, groups p = 0.84, equal time gap p = 0.68. Groups drift slowly (similarity 0.75 after one quarter, 0.34 after 4.5 years); no data-driven cut beats smooth drift.
- Conviction (bet) groups differ from ownership groups (ARI 0.29), are not driven by size (NMI with size 0.13 against 0.30) and drift faster, but also show no regime effect. They read as investor "tribes" (merger arbitrage, Canadian home bias, income REITs and utilities, blue-chip dividend, ADRs; new by 2026: AI hardware with biotech, midstream with private markets).
- 2026Q2, largest component: ownership diameter 14, radius 7; conviction diameter 8, radius 5.
- Co-movement (groups at t, returns t to t+1, 18 periods): sectors explain more than tribes (8.9% vs 5.9% above random groupings), but tribes add 3.8% on top of sectors and size (significant in 17 of 18 periods) and beat sectors in the 2022 and 2025 stress quarters.
