# Sources and code-reuse log

Keep this current. It feeds the data-source and code-reuse disclosures in the report.

## Data (accessed 4 Nov 2026)

### Topic 1: World Bank Contract Awards
- Catalog: https://datacatalog.worldbank.org/search/dataset/0037797/world-bank-contract-awards
- API: https://search.worldbank.org/api/contractdata
- Licence as recorded in the project handoff: CC BY 4.0.

### Topic 3: SEC Form 13F and mapping files
- 13F data sets: https://www.sec.gov/dera/data/form-13f
  - Release 1 Jun-31 Aug 2026 (report period 30 Jun 2026)
  - Release 1 Mar-31 May 2026 (report period 31 Mar 2026)
- Readme: https://www.sec.gov/files/form_13f_readme.pdf
- Fails-to-deliver files, used for CUSIP to ticker: https://www.sec.gov/files/data/fails-deliver-data/cnsfailsYYYYMM[a|b].zip
- Company tickers, used for ticker to CIK: https://www.sec.gov/files/company_tickers.json
- Financial Statement Data Sets 2026 Q2 (`sub.txt`), used for CIK to SIC: https://www.sec.gov/files/dera/data/financial-statement-data-sets/2026q2.zip
- SEC CIK lookup file (name to CIK, includes historical names): https://www.sec.gov/Archives/edgar/cik-lookup-data.txt
- SEC submissions API (SIC per CIK): https://data.sec.gov/submissions/CIK##########.json
- OpenFIGI mapping API (CUSIP to ticker and security type): https://api.openfigi.com/v3/mapping
- Fama-French industry definitions (Siccodes12, Siccodes48): Kenneth R. French data library, https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
- Terms of reuse: not yet checked. The readme carries an accuracy disclaimer but no licence.
- SEC rejects automated requests without a contact in the User-Agent header (HTTP 403). Download scripts must read the contact from an environment variable, so that no address is committed to the repository.

## Existing code reused
- No code for either dataset was copied from the internet or from existing projects.
- Code in `project/feasibility/` was written for this project with AI assistance (see `AI_USE.md`).

## Libraries
Python 3.11.9, NetworkX 3.6.1, pandas 2.2.3, NumPy 2.4.6, SciPy 1.15.2, scikit-learn 1.8.0.

## Algorithms (cite in the report)
- Louvain: Blondel et al. (2008), as cited in Lecture 4; `networkx.community.louvain_communities`.
- Label propagation: Raghavan, Albert and Kumara (2007), as cited in Lecture 4; `networkx.community.asyn_lpa_communities`.
- PageRank: Brin and Page (1998), as cited in Lecture 3; `networkx.pagerank`.
- Adjusted Rand index and normalised mutual information: scikit-learn implementations. Add the primary references.

## Filing rules used (6 Nov 2026)
- The SEC 13F readme (https://www.sec.gov/files/form_13f_readme.pdf) defines `AMENDMENTTYPE` in the cover page data: RESTATEMENT replaces the report, NEW HOLDINGS adds positions. `s01` follows that reading. Check the exact wording in the readme before the report is written.
