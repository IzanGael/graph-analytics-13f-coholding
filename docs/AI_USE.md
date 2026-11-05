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
