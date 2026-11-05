# Handoff for a new chat (written Thu 5 Nov 2026, evening)

You are taking over a master's course project mid-way. Read this file first, then do the **independent audit** described in section 9 **before** any new work.

## 1. The project in two lines
Graph Analytics (Albert School x Mines, 2026). Build a stock co-holding network from SEC Form 13F filings and test whether groups of stocks formed by shared investors differ from official sectors, persist over time, and predict co-movement better than sectors do.
**Team of three** (the instructions PDF says two; the teacher said in class that three is allowed; written confirmation is still missing): Izan Gael Rooke Mora (repo owner, the person you talk to), Oussama Maaref, Ryan Ebanda. Emails are in `docs/STATUS.md`.

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

**Data is not in the repo.** On Izan's laptop it is in `data/raw` (SEC ZIPs) and `data/interim` (cleaned parquet, graphs). A 0.72 GB bundle of the cleaned data was built in `export/` (ignored by git) for Google Drive folder https://drive.google.com/drive/folders/1KfR8t2zsmP6KvTb8sfD-eMcY95sI3sG7 ; **Izan still has to upload the zip and set sharing**.

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
1. **Audit first** (section 9), then agree the plan with Izan.
2. Required measures on the main graph, per quarter and for 2026Q2 in detail: connectivity and components, **diameter and radius** (decide convention: hops vs weighted distance; per component vs the largest connected group; the graph is undirected, simple, weighted by z), degree/strength, betweenness, closeness, eigenvector, PageRank, core-periphery (k-core). Decide how to read centralities given they track popularity partly. The 49 isolated stocks: who are they?
3. **Communities**: Louvain (with several seeds) and label propagation; modularity; stability across seeds; interpret by sector, by size tier, and by top names. Compare with Fama-French sectors (NMI/ARI with a shuffled-label baseline) and with size tiers.
4. **Persistence**: do communities of quarter t reappear at t+1 (ARI on common stocks)? Compare with a null.
5. **Co-movement and the falls-and-selling idea** (Izan's addition): returns from filings are only a proxy (value/shares, quarterly). Communities from quarter t against returns in t to t+1 only (no look-ahead), versus sectors; down quarters (2022 is in the window); selling by community from changes in shares held. Report as association, never cause. Needs a thoughtful proxy-quality check.
6. **Sensitivity checks**: k = 10 and 25 (graphs already built), top 500 and 2,000 stocks, Newman weights (1/(n-1) per manager), the old 10-200 manager rule.
7. Rewrite or delete `src/drafts/` scripts; add tests as useful.
8. **Report** (template, max 15 pages) and **slides** (8 minutes, three speakers).
9. Housekeeping: upload the Drive zip and set sharing, test the README link logged out; confirm the teacher's written OK for three people; check SEC reuse terms; verify citations (cited from memory so far: Newman 2001 weights, Saracco et al. 2015/2017 bipartite configuration model, Blondel et al. 2008 Louvain, Raghavan et al. 2007 label propagation, Tumminello et al. 2011); decide public or private for the repo; **delete `CLAUDE.md` before submission** (Izan's request; it stays in git history unless history is rewritten or the repo recreated; decide how); finish the README; keep logs current.

## 7. Known weaknesses and open doubts (from our own review; probe these)
- Thresholds in the value flags (5x own median, 5x neighbours, 2x price, 20% of value) were never tuned; Bank of Montreal (price rule, many quarters) and JPMorgan 2026Q2 (spike, $1.7tn) may be false flags. No outside check of quarterly totals against published market values.
- 27 fuzzy company matches were not individually verified; FIGI fallback tickers could collide with unrelated US tickers (unchecked); coverage statistics are computed on the top 1,000 non-funds while the graph takes the top 1,000 operating names, so big unmapped issuers (First Republic) drop out silently.
- Survivorship: the universe is re-ranked each quarter and unmapped names skew to acquired companies (improved a lot by name matching, not eliminated).
- The z-score heavy tails (37% of pairs beyond +-3) mean the chance model leaves lots of structure; some of it is manager style by market cap. Does the project answer "different from sectors" or just "different from size"? Needs a size control.
- Returns are inferred from filings (value divided by shares, medians), valid only for quarterly horizons.
- Long positions only, large US-reporting managers only, up to 45 days of reporting delay, quarter-end snapshot.
- A 13F manager is a filing institution, not a fund (JPMorgan files as one).
- The first-quarter and 2026Q2 median fixes could never use both neighbours; end quarters are handled by the row-level check only.
- Solver for the chance model is stopped by an iteration cap (8,000), with relative degree error below 0.009% in every quarter.

## 8. Environment facts
- Run order and timings are in `README.md`. Rebuild from raw ZIPs takes about 20 minutes plus about 30 minutes for a first OpenFIGI/SEC mapping run (cached afterwards).
- `src/s04_build_graphs.py` takes about 10-15 minutes for 19 quarters and writes graphs under `data/interim/graphs/`.
- If the data folders are missing (new machine), download the Drive bundle (once uploaded) into `data/interim/` or rerun `s01` onwards.

## 9. Your first task: an unbiased audit
Before touching anything, read the course documents again and the whole repo, then give Izan a **short, ranked report** of:
1. **Mistakes**: wrong code, wrong maths, wrong claims, misread data, reversed labels, anything that would change a number or a conclusion. Give file and line or the exact figure, the evidence, and a concrete failure scenario. Distinguish what you verified (by running or reading) from what you suspect.
2. **Big improvements**: design choices that would make the project more meaningful, more defensible, or cheaper in the time left (for example: is the question truly answerable with this data and graph? is there a simpler or stronger design? is a size control missing? are the centrality and community choices appropriate? is the Neo4j option worth anything here?). Be critical of our decisions and of the numbers in this file; several were written under time pressure.
3. **Gaps against the assignment**: any required item in the instructions or the template that we are not yet covering, and any rule we might break (disclosures, citations, page limit, defense format).
4. A recommended plan for the remaining time, with the order of work and what to cut if time runs short.
Do not change code or data during the audit. Present findings, then wait for Izan's choices and follow the working rules in section 5.
