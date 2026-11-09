# AI-use log

Notes for the AI-use statement in the report. Add an entry for each use.

## 4 Nov 2026: Claude Code (model Claude Opus 5.5)
- Read the assignment and lectures and summarised the constraints.
- Wrote the feasibility scripts in `project/feasibility/` and ran them: API probing, data profiling, and first graphs for both topics.
- Produced the comparison of the two topics and a recommendation. The choice of topic remains with the students.

## 4-5 Nov 2026: Claude Code (model Claude Opus 5.5)
- Wrote the pipeline scripts in `src/` (download and cleaning of the 13F data, sector mapping, the size-aware chance expectation and its tests) and the two EDA notebooks, and ran them. The students chose each analysis decision (quarters, filters, fixes, which proposals to apply); Claude proposed options with trade-offs and implemented the chosen one.
- Diagnosed data problems (unit errors, wrong median prices, one inflated filer) and proposed fixes.
- Proposed company-to-SEC matches from the SEC name file; the students approved which to apply. Five large names were checked by hand against SEC records.
- A second Claude instance reviewed the code read-only and reported defects, which were then fixed.
- Claude cited methods from memory (Newman 2001; Saracco et al. 2015, 2017; Blondel et al. 2008; Raghavan et al. 2007). These references must be verified before they go in the report.

## 5-6 Nov 2026: Claude Code (model Claude Opus 5.5), independent audit and first fix
- Audited the project read-only: re-read the course documents, read the code, rebuilt the 2026Q2 graph from the holdings and compared it with the stored one, and ran rough diagnostic checks (name matching, community overlap with sectors and size, persistence, a pilot of returns against communities). The pilot scripts are in a scratch folder and are not project results.
- Found four wrong sector labels (see STATUS, audit fix 1) and, with Izan's approval, corrected three by hand against SEC records and added a 50-holder minimum to the universe. Izan approved the fix and supplied the SEC contact address for the lookups; it was passed only through the environment and is not stored in the repository.

## 6 Nov 2026: Claude Code (model Claude Opus 5.5), amendment handling
- Found that the pipeline dropped 13F amendments; wrote the `filing_chain` rule in `src/s01_download_13f.py` to use restatements and new-holdings amendments; tested it on 2026 Q1; reran the pipeline. Izan approved the approach.

## 6-8 Nov 2026: Claude Code (model Claude Opus 5.5), regimes, conviction graph, co-movement (Oussama)
- Summarised the repository and data structure, proposed a Neo4j graph model, and explained the methods (z-scores, Louvain, ARI) in plain terms.
- Wrote and ran the scripts in `src/regimes/`: regime tests on links and groups, the data-driven investor calendar, the conviction graph and its tests, tribe profiles, graph measures, returns from filings and the co-movement test.
- The students chose each step: adding regimes, reversing the approach, moving to allocations (Oussama's idea), the overweight rule and threshold, and the theme names of the bet groups. Results that went against the hypotheses are reported as such.

## 9 Nov 2026: Claude Code (model Claude Sonnet 5), Neo4j defense demo (Ryan)
- Exploration/visualization only, for the oral defense slides; does not touch `src/`, `data/`, or `results/` and is not part of the graded pipeline or its numbers.
- Wrote `neo4j/build_demo_data.py`, which recomputes the conviction graph (same formulas and parameters as `src/regimes/conviction_build.py` and `conviction_profiles.py`) for two quarters only (2022Q2, 2026Q2), because the intermediate `graphs_conviction/*.parquet` caches those scripts write are gitignored and were not present on this machine. Identified the "merger arbitrage" tribe in both quarters from a known ticker, cross-checked against `results/regimes/conviction/bet_group_profiles_2022Q2_2026Q2.csv` and `results/regimes/metrics/centralities_conviction_2026Q2.csv`, and exported Stock/Manager/Tribe/Sector nodes and BETS_ON/CO_BET/IN_TRIBE/IN_SECTOR relationships for the four planned demo scenes (one tribe, one stock's links, the full tribe map, the same tribe two years apart) to `neo4j/export/*.csv`.
- Installed a portable JDK 21 and Neo4j Community 5.26 under `~/opt` (user-space, no root) and loaded the CSVs; the four saved queries are in `neo4j/scenes.cypher`. The Louvain communities were recomputed with the same code and random seed as the graded scripts but reproduced slightly different group sizes (e.g. the 2022Q2 merger-arb tribe came out as 14 stocks here, not 16 as in the committed `bet_group_profiles` CSV) -- the kind of library/Python-version sensitivity already noted in `docs/STATUS.md`'s reproduction note. This demo's own numbers were not used in, and do not change, any reported result.
- With Ryan's approval, installed three missing Chrome runtime libraries (`libnspr4`, `libnss3`, `libasound2t64`, via `sudo apt-get`) and a portable Chromium (via Playwright's downloader, no root) to open Neo4j Browser as a normal window through WSLg, rather than exposing the Neo4j server to the network -- the safer option was chosen deliberately over binding Neo4j to all interfaces.

## 9 Nov 2026: Claude Code (model Claude Opus 5.5), slides and written report (Oussama)
- Built the defense slides in Canva from the team's template (text, speaker notes, figures and tables in the template palette, `report/make_figures.py`), with the students choosing the structure and checking each slide.
- Drafted the written report on the course LaTeX template from the project results, compiled it, checked the references online and corrected two numbers against the results files. The students reviewed the content, the claims and the AI-use statement.
- Removed `CLAUDE.md` (Izan's request) and flagged `src/drafts/` as unused, in a pull request for Izan to review.
