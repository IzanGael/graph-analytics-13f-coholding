# Project status

Last updated: 4 Nov 2026.

## Essentials
- **Team:** Izan Gael Rooke Mora (irooke@albertschool.com, repo owner), Oussama Maaref (omaaref@albertschool.com), Ryan Ebanda (rebanda@albertschool.com).
- **Deadlines:** report PDF on Tue 10 Nov 2026 at 8:00 (Paris), max 15 pages. Defense the same day, 14:00-17:00: 8 min talk, 2 min questions, everyone speaks.
- **Course files** (not in this repo; in the parent course folder): `Instructions-graphs-project-2026.pdf`, `written-report-template.docx`, the lectures and the lab.
- **Question:** do shared institutional holdings define groups of stocks that differ from official sectors, persist over time, and predict co-movement better than sectors do?

## Decisions so far
| Decision | Choice | Why |
|---|---|---|
| Topic | SEC 13F co-holding network, not World Bank contracts | In the feasibility test, 13F communities were interpretable and more stable (quarter-to-quarter ARI 0.42). World Bank country communities were not (ARI 0.19 between periods), 95% of firms worked in one country, and the hubs were audit firms. |
| Software | NetworkX | Allowed by the course, and enough at this graph size. |
| Quarters | 19, 2021 Q4 to 2026 Q2 (only 2024 Q2 onwards downloaded so far) | Chosen by Izan. Gives 18 quarter-to-quarter tests and adds the 2022 decline for the falls analysis. Costs a format fix for values in thousands and some survivorship bias. |
| Filters applied | Original 13F-HR for the quarter, no options, shares only, valid rows | Reviewed and accepted by Izan. |
| Value units | Keep reported value; rescale by 1,000 only when that brings it close to shares x median price | Chosen by Izan after plain recomputation proved exposed to misreported shares. |
| Fake CUSIPs | Remove placeholder codes | At most 0.034% of rows; a single filer's Philips row adds little to shared-holder links. |
| Lowercase CUSIPs | Uppercase, then sum | Evidence shows the same securities: at most 0.5% of rows, few true duplicates. |
| Dataset accepted | 19 quarters after `s01` + `s01b` (units, wrong medians, three flag rules) | Izan accepted on 5 Nov. Known limits to cite in the report: 5x/2x/20% thresholds are untuned; Bank of Montreal (price rule, many quarters) and JPMorgan 2026 Q2 (spike, $1.7tn) may be false flags; no outside market-total check. Flagged filers keep links and lose only value. |
| Working style | One step at a time (see `CLAUDE.md`) | The students decide and learn. |
| Final analysis | Add a test of falls and selling: do communities fall together in down quarters, and do communities sold more do worse? | Izan's idea, and the most direct test of "fall together". Reported as association, not cause. Depends on how many down quarters the window has. |

## Where things stand
- **Done and run end to end from the raw ZIPs:** `s01` (download and clean, 19 quarters), `s01b` (fix wrong prices, flag unreliable filers), `s02` (sector mapping), `s03a` (test of the size-aware chance expectation), `s03b` (tail probe and backbone options). Data lives in `data/interim/` (not committed).
- **Drafts in `src/drafts/`, never run, not part of the pipeline:** `s03_sensitivity.py`, `s04_main_analysis.py`, `s05_persistence_returns.py`. They still use the superseded 10-200 manager rule and must be rewritten on top of `gutils.shared_holder_z_bicm`.
- **Main graph (k = 15) and the k = 10 / 25 variants are built for all 19 quarters** (`s04_build_graphs.py`). **Next:** required metrics (components, diameter, radius, centralities, core-periphery), communities (Louvain, label propagation), comparison with sectors and with size tiers, persistence across quarters, the falls and selling test, then sensitivity checks, report and slides. A fresh-eyes audit is the first task of the next session (see `docs/HANDOFF.md`).

## Known problems to resolve
- Centrality rankings changed heavily with the manager filter in the feasibility test (Voya versus PepsiCo at the top of PageRank), so a "systemic stock" claim is not yet supported; redo on the new graph.
- The "fall together" result from the feasibility test was one in-sample quarter with look-ahead bias; the proper test has not been built.
- Size partly drives communities (NMI 0.17 with size tier), so the report must control for it.
- The SEC's reuse terms have not been checked.

## EDA so far (`notebooks/01_eda.ipynb`)
- The 19 quarters are comparable, with growth from the first to the last: managers +32%, positions +45%. Managers jump by about 600 each Q4; the cause has not been checked.
- Filters keep 85.7% of rows in 2026 Q2.
- Using a stand-in universe that still includes ETFs (rerun on cleaned values), the 10-200 manager rule keeps 68.3% of managers but only 9.5% of the money and 8.5% of stock pairs. Managers with 501+ positions hold 79.9% of the money and create 69.3% of pairs. 188 of 8,737 managers are flagged unreliable on value and count 0 money there (JPMorgan in 2026 Q2 among them).
- A 13F "manager" is a filing institution, not a single fund (JPMorgan and Morgan Stanley file as one).

## Stock-side EDA (`notebooks/02_eda_stocks.ipynb`, 2026 Q2)
- 12,713 issuers; 4,702 have a single holder. The top 1,000 by value hold 92% of the money and have 611+ holders each (one exception, Hershey Class B, 1 holder).
- About 76 of the top 1,000 have fund-like names (12.4% of their value); name-based proxy only.
- Raw shared holders track popularity (Spearman 0.86 against expected-by-popularity). Of the top 5,000 raw pairs, 91% involve one of the 50 most-held stocks, against 5% by z-score. Observed counts sit above expected for almost every pair, so the independence null ignores manager breadth: this is the case for weighting by portfolio size.
- Notebook 01 was rerun on cleaned values on 5 Nov.

## Sector mapping (`s02`, ran 5 Nov)
- 2,630 candidate issuers (top 1,800 per quarter, 19 quarters); output `data/interim/issuer_map.parquet`, `results/mapping_coverage.csv`.
- SIC coverage of the top 1,000 non-fund stocks: 87.8% in 2021 Q4 rising to 96.2% in 2026 Q2. 85-158 funds per quarter flagged in the top 1,800.
- Unmapped names skew to acquired or delisted companies (Activision, Pioneer, Xilinx, Twitter, VMware, Splunk, Citrix): survivorship bias in the early quarters. Still unmapped and current: Exxon, Accenture, Honeywell, Seagate, Thomson Reuters; cause not yet diagnosed.
- 191 CIKs came from name matching and have not been spot-checked.
- Bulk SEC name file (`cik-lookup-data.txt`, 1.07m names) tried via `src/s02b_name_candidates.py` for the 427 unmapped non-fund stocks: 219 unique matches, 117 ambiguous, 91 none (`results/name_candidates.csv`). Proposals only, nothing merged. The CIK shown for ambiguous rows is just the lowest number and is often wrong (Honeywell, Accenture). Truncated 13F names ("SEAGATE TECHNOLOGY HLDNGS PL") and abbreviations ("CANADIAN PAC RY LTD") cause the no-matches. The earlier failure of Exxon, Accenture and Honeywell was spelling, not a bug in OpenFIGI.

- **Applied (Izan, 5 Nov):** name-file proposals of types unique (226), listed-first (26) and fuzzy (27, minus four judged wrong: Select Medical, Retail Opportunity Investments, Horizon Therapeutics, Cushman & Wakefield) via `data/manual_overrides.csv`, then `s02` rerun. Operating issuers 2,028 to 2,298 of 2,630; coverage of the top 1,000 non-funds now 95.9% (2021 Q4) to 99.0% (2026 Q2). Still unmapped and large: Brookfield, Johnson Controls, Royal Caribbean, CRH, Ferguson, First Republic. Previous map kept as `issuer_map_before_overrides.parquet` (local only). The 27 fuzzy matches were not individually verified.

- **Six large names (5 Nov):** Brookfield, Johnson Controls, Royal Caribbean, CRH and Ferguson were hand-checked against SEC submissions and added (`method = hand-checked` in the overrides file). First Republic Bank stays unmapped: its SEC record has no SIC (bank regulated elsewhere). Coverage of the top 1,000 non-funds is now 96.3% (2021 Q4) to 99.3% (2026 Q2); 2,303 operating issuers.

## Tail probe and backbone options (`src/s03b_tail_probe.py`, 2026 Q2)
- Simulating graphs from the fitted model gives 0.1-0.2% of pairs beyond |z|>3 and a spread of 1.01, so the variance formula is right; the real data (17.4% above 3, 20.4% below -3, spread 3.46) has genuine structure the null does not know.
- Mean z by stock-size tier (tier 0 = SMALLEST fifth, tier 4 = LARGEST; an earlier version of this note and of a chat message had it backwards, caught by the code review): largest-with-largest +2.7, fourth-with-fourth +2.1, smallest-with-smallest -0.6, largest-versus-smallest -2.2. The big stocks share one crowd of holders and the smallest avoid them. Managers specialise by market-cap, so communities may partly reflect size class. Same sector mean z 0.2 against -0.3 across sectors, a weak effect. The most negative pairs all involve Enterprise Products Partners (an MLP with a niche holder base).
- Backbone options: global z>3 keeps 86,688 edges (mean degree 173; Louvain modularity 0.32; NMI with sectors 0.04); global z>10 leaves 762 isolated stocks; z>20 leaves 3 edges. Top-k per stock with z>3 (k = 10 / 15 / 25): 7,074 / 10,136 / 16,000 edges, modularity 0.65 / 0.62 / 0.57, NMI with sectors 0.13 / 0.14 / 0.12, degree-versus-holders Spearman 0.13 / 0.17 / 0.22 (global rules: 0.41-0.58). All top-k options keep a 935-stock largest component, 49 isolated stocks and diameter 14. Not yet looked at: who the 49 isolated stocks are.

## Code review and clean rebuild (5 Nov)
- An independent read-only review of `src/` found: (1) the median fix in `s01b` was not idempotent and flip-flopped on securities present in only one neighbouring quarter (SPAC liquidations, delistings); fixed by requiring both neighbours, never correcting an end quarter from one, and repeating passes until nothing changes; (2) tier labels in `s03b` were reversed (fixed); (3) coverage statistics are measured on the top 1,000 non-funds, but the graph takes the top 1,000 operating names, so large unmapped issuers (First Republic) drop out silently; (4) FIGI fallback tickers could in principle collide with unrelated US tickers (not checked); (5) latest filing was chosen by accession number, now by filing date (0-3 repeat filers per quarter, so negligible); (6) logged totals in `quarter_log.csv` are before the `s01b` median fix; (7) solver now raises on zero-degree nodes; (8) `graphlib.py` renamed `gutils.py` because it shadowed the standard library.
- All 19 quarters rebuilt from the ZIPs (`s01`, then `s01b`, `s02`, `s03a`), all exit 0. The median fix settled in 3 passes (32,957 rows, then 26, then 0). Quarterly reliable totals, mapping coverage (96.3% to 99.3%) and the null-test numbers reproduced the earlier incrementally built dataset exactly, so the earlier faulty runs left no material trace. Backup of the pre-rebuild data kept locally in `data/interim/backup_before_fixedpoint`.
- No automated tests exist; the evidence is that the whole pipeline runs end to end from raw ZIPs and reproduces earlier numbers.

## Filter 8, backbone size (decided 5 Nov, Izan: "do it")
Main graph: each stock keeps its top 15 partners with z > 3 under the size-aware chance model, all managers, top 1,000 operating companies per quarter. Sensitivity checks: k = 10 and 25, top 500 and 2,000 stocks, Newman weights, and the old 10-200 manager rule. Set in `src/config.py` (`RECIPE`, `SENSITIVITY_K`). Reason: global cut-offs fail, and k = 15 balances readability and coverage; modularity should not be used to pick k because sparser graphs always score higher. Still to look at: who the 49 stocks with no partner are.

## Main graph built for all 19 quarters (`src/s04_build_graphs.py`, `results/graph_summary.csv`, `figures/f9_graph_over_time.png`)
- The chance model solver was made about 10x faster by grouping managers of equal size (same answer; four tests in `tests/test_gutils.py`; the 2026 Q2 numbers reproduced exactly). Solver error in every quarter under 0.009% (this checks that expected holders per stock and per manager size match the observed counts; it is numerical precision, not a measure of fit).
- Every quarter: 1,000 stocks, 6,100 to 8,200 managers, about 9,500 to 10,100 links with top-15 (about 19-20 per stock), 903 to 939 stocks in the biggest connected group, 49 to 82 stocks with no link (more in 2021-22, 49 in 2026 Q2), 55 to 89 components.
- Quarter to quarter: 87-93% of the stocks are the same; of the links among stocks present in both, Jaccard 0.47-0.52 (about two thirds of a quarter's links reappear next quarter).
- Not yet done: who the isolated stocks are; diameter, radius, centralities, communities.

## Filters still to review with the students
Izan does not yet accept these three. Explain the why behind each, with evidence and alternatives, before relying on them:
- Top 1,000 operating companies by value, without ETFs and funds. **Decided 5 Nov (Izan): top 1,000 re-ranked each quarter as the main universe; run top 500 and top 2,000 as sensitivity checks.** Evidence: top 1,000 hold 92% of money in 2026 Q2 (top 500: 84%, top 3,000: 99%); the 1,000th stock has 611 holders. 1,000 was a round number, hence the checks. Quarter-to-quarter comparisons use stocks present in both quarters; the overlap is not yet measured.
- Managers (filter 7). **Decided 5 Nov (Izan): main method = size-aware chance expectation (bipartite configuration model: expected shared holders given both each stock's popularity and each manager's portfolio size; cite Saracco et al. 2015/2017, to verify). Robustness checks: (A) Newman weights, each manager adding 1/(n-1) per pair (Newman 2001, to verify), and (C) only managers with 10-200 positions.** All managers kept in the main graph. Built and tested on 2026 Q2 in `src/s03a_null_test.py` (`results/null_test.csv`, `figures/f7_null_calibration.png`): median observed/expected shared holders 0.99 against 4.74 for the old null; top pairs are spin-offs and same-industry peers (Honeywell/Honeywell Aerospace, GE Aerospace/GE Vernova, Sandisk/Western Digital, Verizon/AT&T). Caveats: solver hit its 3,000-iteration cap with degree errors under 0.03%; 17.4% of pairs have z>3 and 20.4% z<-3 (a perfect model would give about 0.3% each), so either real manager styles or understated variance; popularity not fully removed (top-50-held stocks in 23.7% of the top-5,000 pairs, against about 10% by chance); the top-5,000 pairs are 24.9% same-sector against 13% baseline (31.2% under the old null). `src/config.py` and the other scripts still use 10-200 and must be changed.
- Backbone: each stock keeps its 15 strongest links, with z > 3.

## Data problems found across the 19 quarters (not yet fixed)
Columns, tables and date formats are identical across all quarters. Details are in `results/quarter_inspection.csv` and `results/unit_check.csv`, from `src/inspect_quarters.py`.
1. **Value units are inconsistent.** 68-87 filers used dollars before the 2023 switch, and 339-1,293 still use thousands after it. The date-based conversion now in `s01` wrongly multiplies the early dollar filers: 2021 Q4 sums to $444tn, with shares x price near $65tn. A few filers also misreport `SHARES` (2026 Q2: shares x price gives $116tn against $72.6tn reported). Do not trust summed values before this is fixed. The median prices checked look right.
2. **Fake CUSIPs:** placeholders such as `000000000` hold cash, "NONE" and similar rows (about 140-820 rows per quarter in the three quarters checked).
3. **Zero-value rows:** 2.33% of long rows in 2021 Q4 against 0.27% in 2026 Q2, probably from rounding to thousands.

The one-quarter return result from the feasibility test (16.5%) used summed values and should not be relied on.

## Next step, waiting on the students
The three agreed fixes are built into `s01` and all 19 quarters rebuilt. Totals fell from $330-443tn to $39-71tn in the 2021 Q4-2022 Q3 quarters, but some jumps remain (2022 Q2 $71tn, 2023 Q2 $58tn) because a few filers inflate value and shares together, for example Bank Julius Baer at $16.6tn in 2023 Q2 (`src/inspect_totals.py`). Decided and applied (`src/s01b_flag_inflated.py`, run after `s01`): filers above 5x their own median total keep their links but lose value in rankings and money shares; 1,437 filer-quarters flagged. Then Izan chose to fix 2022 Q2: `s01b` now first corrects securities whose median price is about 1,000x off neighbouring quarters (mostly ETFs). Flags fell to 1,007 filer-quarters; 2022 Q2 is now $35.7tn. The 2021 Q4 excess traced to one filer, Metatron Capital SICAV (8 rows, $11.84tn; e.g. $7.7tn in Microsoft), which the own-median rule could not flag because it filed in one quarter. `s01b` now adds a spike rule (total above 5x both neighbouring quarters) and a price rule (over 20% of a filer's value in rows priced above 2x the security's median). Flags rose to 1,641 filer-quarters (635 only from the new rules); reliable 2021 Q4 is $44.9tn against $42.5tn in 2022 Q1. Possible false flags not yet inspected: Bank of Montreal (price rule, many quarters), JPMorgan 2026 Q2 (spike, $1.7tn). Flagged filers keep their links and only lose value for rankings. Next: accept or tune, then stock-side EDA. The 01_eda notebook needs rerunning: its money shares used the old values.

## Open decisions
- **Repo visibility:** public at submission, or private with graders invited. Undecided.

## Data for graders (5 Nov)
Processed-data bundle built locally in `export/` (not committed): `processed_13f_2021Q4-2026Q2.zip`, 0.72 GB, 40 files, extraction verified identical, plus `MANIFEST.txt` with SHA-256 hashes. Drive folder created in Izan's account with the manifest inside: https://drive.google.com/drive/folders/1KfR8t2zsmP6KvTb8sfD-eMcY95sI3sG7 . **Open:** Izan must upload the zip into that folder by hand (the Drive connector cannot carry 0.7 GB), then set sharing so graders can open it (the folder is private right now), and the README link must be tested while logged out.

## Before submission
- [ ] Upload `export/processed_13f_2021Q4-2026Q2.zip` to the Drive folder, set sharing, test the link logged out.
- [ ] **Delete `CLAUDE.md` from the repo** (requested by Izan). It would remain in the git history unless the history is rewritten or the repo is recreated, so decide how to handle that.
- [ ] Get the teacher's written confirmation that a group of three is allowed; the instructions PDF says two.
- [ ] Invite Oussama and Ryan to the repo (Izan is doing this).
- [ ] Settle repo visibility and check that the link works for someone logged out or invited.
- [ ] Complete the README reproduction steps and the data link.
- [ ] Add the AI-use and code-reuse statements to the report, and all three names and emails.
- [ ] Remove this file too if it should not be graded.
