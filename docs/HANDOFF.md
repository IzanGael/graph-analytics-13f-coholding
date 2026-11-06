# Handoff for a new chat (updated Fri 6 Nov 2026, afternoon)

You are taking over a master's course project mid-way. Read this file first, then `docs/STATUS.md` (its last section is the current state). The independent audit (section 9) was done on 5 Nov; its findings are in STATUS and in the sections below.

## 1. The project in two lines
Graph Analytics (Albert School x Mines, 2026). Build a stock co-holding network from SEC Form 13F filings and test whether groups of stocks formed by shared investors differ from official sectors, persist over time, and predict co-movement better than sectors do.
**Team of three** (the instructions PDF says two; the teacher allowed three; Izan reports having the written confirmation): Izan Gael Rooke Mora (repo owner, the person you talk to), Oussama Maaref, Ryan Ebanda. Emails are in `docs/STATUS.md`.

## 2. Deadlines
- **Written report: Tue 10 Nov 2026, 08:00 Paris**, PDF, max 15 pages, template `written-report-template.docx` (sections: Abstract, Introduction, Dataset Presentation, Description of the Analysis, Results, Conclusions, References), names and emails of all authors, GitHub link, AI-use statement.
- **Oral defense the same day, 14:00-17:00**: 8 min talk + 2 min questions, everyone must speak, slides required.
- Grading: report 60%, defense 40%. Depth and meaning of analysis beat dataset size; superficial analysis is penalised.
- About 4.5 days remain as of this writing. Plan time for the report and slides; do not spend them all on data polishing (we already lost many hours on that).

## 3. Where to find things
**Course documents (outside the repo, in the parent folder of the clone, not committed because they are course material).** Re-read them yourself, do not rely on this summary:
`Instructions-graphs-project-2026.pdf`, `written-report-template.docx`, `lecture-01-graphs-intro.pdf`, `lecture-02-graphs-neo4j.pdf`, `lecture-03-graphs-centrality.pdf`, `lecture04-graphs-community.pdf`, `graphs-practice.pdf` (the lab).
Required content per the instructions: data source and whether existing code was reused (missing either = penalty; uncited code from the internet = grade zero); question; how the graph is built (nodes, edges, weights, directed or not, simple graph or multigraph, justified); number of nodes and edges; connectivity (components); diameter and radius with the convention used (per component or on a chosen component); centralities appropriate to the question, interpreted; communities with the algorithm and an interpretation; software and parameters for reproducibility; GitHub repo with code, data or an external link, and a README explaining how to reproduce. The course covers degree, betweenness, closeness, eigenvector, PageRank, label propagation, Louvain, modularity, core-periphery, NetworkX and Neo4j.

**The repo** (private so far): https://github.com/IzanGael/graph-analytics-13f-coholding . Read in this order:
1. `CLAUDE.md` working rules (see section 5; it is deleted before submission).
2. `docs/STATUS.md` the decision log, every result so far, known problems, and the pre-submission checklist. This is the most complete record.
3. `README.md` how to reproduce. `docs/SOURCES.md` data and method sources. `docs/AI_USE.md` AI-use log for the report statement.
4. `src/` pipeline (run order in README), `src/gutils.py` shared maths, `src/config.py` settings, `tests/test_gutils.py`, `src/exploration/` one-off diagnostics, `src/drafts/` old scripts never run.
5. `results/` tables, `figures/` charts, `notebooks/` two EDA notebooks, `data/manual_overrides.csv` reviewed company matches.

**Data is not in the repo.** On Izan's laptop it is in `data/raw` (SEC ZIPs) and `data/interim` (cleaned parquet, graphs). A bundle of the cleaned data (`export/processed_13f_2021Q4-2026Q2.zip`, about 737 MB, with `export/MANIFEST.txt`, built 6 Nov after the rebuild and verified) is ignored by git. It is uploaded at https://drive.google.com/file/d/1K8UPFQDs8XA4jv1i86lP-VDyOBAldtag/view?usp=sharing (Izan, 6 Nov; sharing not yet tested logged out) and in Google Drive folder https://drive.google.com/drive/folders/1KfR8t2zsmP6KvTb8sfD-eMcY95sI3sG7 ; the 5 Nov zip was replaced by the 6 Nov build (Izan uploaded it). Sharing still needs checking.

## 4. What has been done, in order
1. Compared two topics (World Bank contracts, rejected; SEC 13F, chosen) with a feasibility test of both.
2. Downloaded 13F data for **19 quarters, 2021Q4 to 2026Q2** and built the cleaning pipeline (`s01`, `s01b`). Problems found and fixed with the user's approval: value units (thousands before 3 Jan 2023, but many filers inconsistent), wrong median prices (e.g. ETFs 1,000x off in 2022Q2), one filer inflating 2021Q4 by $11.8tn, fake CUSIPs removed, lowercase CUSIPs uppercased. Values are used only for ranking stocks by size; **links never depend on value**. Unreliable filers keep their links and lose their money. The pipeline was rebuilt from the raw ZIPs and reproduced earlier numbers exactly.
3. **Independent read-only code review** (a second Claude) found real bugs, all fixed: the median fix flip-flopped (now needs both neighbouring quarters, repeats until stable), reversed tier labels, a module name shadowing the standard library (`graphlib` renamed `gutils`), filing-date ordering.
4. **Sector mapping** (`s02`, `s02b`): CUSIP to ticker and security type (OpenFIGI), to company (SEC files and name matching), to SIC, to Fama-French 12 and 48 groups. Coverage of the top 1,000 non-fund stocks 96.3% (2021Q4) to 99.3% (2026Q2). 279 proposals from the SEC name file were approved (4 fuzzy ones rejected by hand), 5 large names checked by hand. First Republic Bank stays unmapped.
5. **Design decisions** (all discussed with Izan, see STATUS): top 1,000 operating companies per quarter re-ranked each quarter (500 and 2,000 as checks); all managers kept; chance model = **bipartite configuration model** (expected shared holders given each stock's popularity AND each manager's portfolio size), because the simple stock-popularity-only null gave 4.7x more shared holders than expected; backbone = **each stock keeps its top 15 partners with z > 3** (10 and 25 as checks) because global cut-offs give a hairball or nothing.
6. **Results so far (2026Q2 unless said):**
   - Chance model: median observed/expected shared holders 0.99 (was 4.74). Strongest pairs are spin-offs and peers (GE Aerospace/GE Vernova, Honeywell/Honeywell Aerospace, Verizon/AT&T, Sandisk/Western Digital).
   - Heavy tails remain: 17.4% of pairs z > 3 and 20.4% z < -3; simulating from the model gives about 0.15% each and spread 1.01 versus 3.46 in real data, so the structure is real and not a variance bug.
   - Size structure: the largest stocks share one crowd of holders; smallest vs largest avoid each other. Communities may therefore partly be size classes. Sector effect on z is weak (mean z 0.2 same sector vs -0.3 different).
   - Backbone comparison (`results/backbone_options.csv`, `figures/f8_backbone_options.png`): global z > 3 keeps 86,688 links (hairball), z > 10 leaves 762 stocks isolated; top-k per stock gives 7,074 / 10,136 / 16,000 links for k = 10 / 15 / 25, modularity 0.65 / 0.62 / 0.57, overlap with sectors (NMI) about 0.13.
   - **Main graph built for all 19 quarters** (`src/s04_build_graphs.py`, `results/graph_summary.csv`, `figures/f9_graph_over_time.png`): 1,000 stocks, 9,500-10,100 links, 903-939 stocks in the biggest connected group, 49-82 isolated stocks, 87-93% of stocks and about two thirds of links persist to the next quarter.
   - EDA: top 1,000 stocks hold 92% of the money; managers with 10-200 positions hold only 9.5% of the money (this rule was dropped).

7. **Rebuild, 6 Nov (current state, supersedes item 6 where they differ):**
   - Filings: the pipeline now uses RESTATEMENT amendments in place of the original, and adds NEW HOLDINGS positions (`filing_chain` in `s01`). JPMorgan 2026Q1 now has 31,365 positions, $1.47tn (was 239, $1.1bn).
   - Sectors: Barrick, AvalonBay and Exact Sciences corrected by hand against SEC records (a ticker mix-up gave them other companies' sectors). A stock needs at least 50 managers (`MIN_HOLDERS` in `config.py`).
   - 2026Q2 main graph (after the Exxon merge): 1,000 stocks, 8,226 managers, 10,134 links, 934 in the biggest group, 47 with no link, 54 groups. 2021Q4: 9,588 links, 79 with no link. Quarter to quarter: 87-93% of stocks stay; about half the links reappear.
   - The 40 big manager-quarter row drops from the earlier scan are down to 32; 8 were explained by amendments, the rest not yet.
   - ExxonMobil listings merged into one company (`ISSUER_ALIASES`, `config.py`), 6 Nov. Numbers below may move slightly after that rebuild; check STATUS for the latest.
   - `s03a`, `s03b` and `s03c` were rerun on 6 Nov on the rebuilt data; their results and figures f7, f8 are current. After the Exxon merge they were rerun again: 17.3% of pairs z > 3 and 20.4% z < -3, links 7,069 / 10,134 / 16,004 for k = 10 / 15 / 25, modularity 0.64 / 0.62 / 0.58, NMI with sectors 0.15 / 0.14 / 0.11, 47 isolated stocks in each.

## 5. How we work (rules, keep them)
- **One step at a time, then stop for Izan's decision.** Never chain steps or finish a full stage alone.
- After each step give a **short recap in very simple words**: what was done, the results, a **graph shown in the chat** when a picture explains better than numbers, then the decision with 2-3 options and trade-offs and your recommendation. Explain technical terms the first time. Izan wants to learn and decide, and asked for short, concise, human replies.
- Data transformations: inspect, explain each problem with the top 3 solutions, decide together, then implement.
- **Be honest**: report failures and results against the hypothesis, say what is unverified, never claim "done" without running the check. There are few automated tests; evidence is that the pipeline reruns end to end and reproduces numbers.
- Commit or push **only when Izan asks**. Back up data before any in-place rewrite.
- **SEC_CONTACT**: the SEC requires a contact address in automated requests; ask Izan for it and pass it through the environment variable. Never write any personal address into a file or commit. (A personal address was deliberately kept out of the repo.)
- Every external source and any reused code goes in `docs/SOURCES.md`; every AI use goes in `docs/AI_USE.md`. No code copied from the internet.
- Windows, PowerShell, Python 3.11, packages in `requirements.txt`. Use `python -W ignore`. Long jobs go in the background. A stray folder `undefined/` created by a plugin sits in the project root and the parent folder; it is ignored locally through `.git/info/exclude` (not in the repo); do not delete or commit it.

## 6. What is left, in suggested order
1. Izan uploaded the new zip to Drive (6 Nov); test the link logged out. `s03a`, `s03b`, `s03c` are already rerun.
2. Required measures on the main graph, per quarter and for 2026Q2 in detail: connectivity and components, **diameter and radius** (decide convention: hops vs weighted distance; per component vs the largest connected group; the graph is undirected, simple, weighted by z), degree/strength, betweenness, closeness, eigenvector, PageRank, core-periphery (k-core). Decide how to read centralities given they track popularity partly. The 49 isolated stocks: who are they?
3. **Communities**: Louvain (with several seeds) and label propagation; modularity; stability across seeds; interpret by sector, by size tier, and by top names. Compare with Fama-French sectors (NMI/ARI with a shuffled-label baseline) and with size tiers.
4. **Persistence**: do communities of quarter t reappear at t+1 (ARI on common stocks)? Compare with a null.
5. **Co-movement and the falls-and-selling idea** (Izan's addition): returns from filings are only a proxy (value/shares, quarterly). Communities from quarter t against returns in t to t+1 only (no look-ahead), versus sectors; down quarters (2022 is in the window); selling by community from changes in shares held. Report as association, never cause. Needs a thoughtful proxy-quality check.
6. **Sensitivity checks**: k = 10 and 25 (graphs already built), top 500 and 2,000 stocks, Newman weights (1/(n-1) per manager), the old 10-200 manager rule.
7. Rewrite or delete `src/drafts/` scripts; add tests as useful.
8. **Report** (template, max 15 pages) and **slides** (8 minutes, three speakers).
9. Housekeeping: upload the Drive zip and set sharing, test the README link logged out; check SEC reuse terms; verify citations (cited from memory so far: Newman 2001 weights, Saracco et al. 2015/2017 bipartite configuration model, Blondel et al. 2008 Louvain, Raghavan et al. 2007 label propagation, Tumminello et al. 2011); decide public or private for the repo; **delete `CLAUDE.md` before submission** (Izan's request; it stays in git history unless history is rewritten or the repo recreated; decide how); finish the README; keep logs current.

## 7. Known weaknesses and open doubts (from our own review; probe these)
- Thresholds in the value flags (5x own median, 5x neighbours, 2x price, 20% of value) were never tuned; Bank of Montreal (price rule, many quarters) may be a false flag. JPMorgan 2026Q2 ($1.7tn, spike rule) is its real full filing and is not flagged by the median rule; the spike flag is still unexamined. No outside check of quarterly totals against published market values.
- 27 fuzzy company matches were not individually verified; FIGI fallback tickers could collide with unrelated US tickers (unchecked); coverage statistics are computed on the top 1,000 non-funds while the graph takes the top 1,000 operating names, so big unmapped issuers (First Republic) drop out silently.
- Survivorship: the universe is re-ranked each quarter and unmapped names skew to acquired companies (improved a lot by name matching, not eliminated).
- The z-score heavy tails (37% of pairs beyond +-3) mean the chance model leaves lots of structure; some of it is manager style by market cap. Does the project answer "different from sectors" or just "different from size"? Needs a size control.
- Returns are inferred from filings (value divided by shares, medians), valid only for quarterly horizons.
- Long positions only, large US-reporting managers only, up to 45 days of reporting delay, quarter-end snapshot.
- A 13F manager is a filing institution, not a fund (JPMorgan files as one).
- The first-quarter and 2026Q2 median fixes could never use both neighbours; end quarters are handled by the row-level check only.
- Solver for the chance model is stopped by an iteration cap (8,000), with relative degree error below 0.009% in every quarter.

## 8. Environment facts
- Run order and timings are in `README.md`. The full rebuild on 6 Nov took about 15 min (`s01`), 8 min (`s01b`), 3 min (`s02`, cached) and 15 min (`s04`).
- `src/s04_build_graphs.py` writes graphs under `data/interim/graphs/`.
- If the data folders are missing (new machine), download the Drive bundle (once replaced) into `data/interim/` or rerun `s01` onwards.
- The backups from 5-6 Nov were deleted on 6 Nov (about 1.7 GB) because the rebuilt data replaced them. Everything can be rebuilt from the raw ZIPs (see README).

## 9. The independent audit (done 5-6 Nov; kept for reference)
The audit was run before new work. Its ranked findings, with what was fixed and what was not, are recorded in `docs/STATUS.md` (audit fixes 1 and 2). The brief was:
1. **Mistakes**: wrong code, wrong maths, wrong claims, misread data, reversed labels, anything that would change a number or a conclusion. Give file and line or the exact figure, the evidence, and a concrete failure scenario. Distinguish what you verified (by running or reading) from what you suspect.
2. **Big improvements**: design choices that would make the project more meaningful, more defensible, or cheaper in the time left (for example: is the question truly answerable with this data and graph? is there a simpler or stronger design? is a size control missing? are the centrality and community choices appropriate? is the Neo4j option worth anything here?). Be critical of our decisions and of the numbers in this file; several were written under time pressure.
3. **Gaps against the assignment**: any required item in the instructions or the template that we are not yet covering, and any rule we might break (disclosures, citations, page limit, defense format).
4. A recommended plan for the remaining time, with the order of work and what to cut if time runs short.
Do not change code or data during the audit. Present findings, then wait for Izan's choices and follow the working rules in section 5.
