# Investor co-holding network (SEC Form 13F)

Graph Analytics project, Albert School x Mines, 2026.
Authors: Izan Gael Rooke Mora and Oussama Maaref.

**Question:** do shared institutional holdings define groups of stocks that differ from official sectors, persist over time, and predict co-movement better than sectors do?

Work in progress. Reproduction steps will be completed with the analysis.

## Layout
- `src/`: analysis pipeline, run in numbered order
- `feasibility/`: exploratory scripts from the topic-selection stage, including the rejected World Bank topic
- `docs/`: source, code-reuse and AI-use logs
- `data/`: not committed; rebuilt by the download scripts

## Setup
SEC rejects automated requests without a contact address, so set your own before downloading:

```powershell
$env:SEC_CONTACT = "you@example.com"
```
