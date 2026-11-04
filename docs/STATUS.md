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
| Quarters | Nine, 2024 Q2 to 2026 Q2 | Gives eight quarter-to-quarter tests. Provisional: not reviewed by the students. |
| Working style | One step at a time (see `CLAUDE.md`) | The students decide and learn. |

## Where things stand
- **Done:** `src/s01_download_13f.py` has run; all nine quarters are in `data/interim/` (not committed).
- **Written but never run, so expect bugs:** `s02_map_sectors.py`, `s03_sensitivity.py`, `s04_main_analysis.py`, `s05_persistence_returns.py`. They were drafted before the step-by-step rule, so review their choices with the students as each step comes up.
- **Provisional, from the feasibility test only:** graph recipe in `src/config.py` (top 1,000 issuers, managers with 10-200 positions in that universe, top-15 z-score partners per stock with z > 3).

## Known problems to resolve
- The feasibility sector mapping covered only 83% of the top 1,000 issuers and missed Exxon, Berkshire, ASML and FedEx. `s02` tries OpenFIGI plus SEC data; it resolved Berkshire and FedEx in a probe but not the Exxon and ASML CUSIPs tried.
- Centrality rankings changed heavily with the manager filter (Voya versus PepsiCo at the top of PageRank), so a "systemic stock" claim is not yet supported.
- The "fall together" result so far is one in-sample quarter with look-ahead bias. `s05` is meant to fix that but has not run.
- Size partly drives communities (NMI 0.17 with size tier), so the report must control for it.
- The SEC's reuse terms have not been checked.

## Next step, waiting on the students
Choose between starting the sector mapping (`s02`) and first going over what the downloaded data contains.

## Open decisions
- **Repo visibility:** public at submission, or private with graders invited. Undecided.

## Before submission
- [ ] **Delete `CLAUDE.md` from the repo** (requested by Izan). It would remain in the git history unless the history is rewritten or the repo is recreated, so decide how to handle that.
- [ ] Get the teacher's written confirmation that a group of three is allowed; the instructions PDF says two.
- [ ] Invite Oussama and Ryan to the repo (Izan is doing this).
- [ ] Settle repo visibility and check that the link works for someone logged out or invited.
- [ ] Complete the README reproduction steps and the data link.
- [ ] Add the AI-use and code-reuse statements to the report, and all three names and emails.
- [ ] Remove this file too if it should not be graded.
