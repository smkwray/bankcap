# H.8 mechanism package

This repository's completed Project 5 deliverable is the H.8 bank-group mechanism screen for
Treasury absorption. The package is designed to answer whether bank-group balance sheets move
differentially around Treasury financing and liquidity-plumbing contexts before any bank-level data
cost is incurred.

## Final project status

The screen is complete as H.8 mechanism context. It is not a Call Report or FR Y-9C bank-level
project, and the current evidence does not authorize bank-level ingestion.

Current generated status:

- Recommendation: partial go for H.8 mechanism context only.
- Target groups: large domestic banks, small domestic banks, and foreign-related institutions are
  present.
- Common target-group sample: 1985-04 through 2026-03, 492 monthly periods and 1,476 group-period
  rows.
- Context-complete share in the common target-group sample: 0.57.
- Fixed coupon-heavy support in the common target-group sample: 0 rows.
- Relative high-bill and low-bill support: 369 rows in each bucket across target groups.
- Relative level-contrast stability: 8 of 12 level contrasts keep the same sign across the common
  target sample and the TGA-complete sample.
- Loan-growth signs are stable across target groups, but securities, deposits, and cash signs are
  mixed.

## Package artifacts

Generated artifacts are intentionally ignored by git:

- `data/derived/bankcap_analysis_panel.csv`
- `output/diagnostics/*.csv`
- `output/figures/h8_ratio_trends.svg`
- `output/figures/relative_bill_share_contrasts.svg`
- `output/reports/h8_go_no_go_report.md`
- `output/reports/h8_mechanism_screen_memo.md`
- `output/reports/h8_mechanism_summary.json`
- `output/reports/h8_mechanism_package_manifest.csv`

The preferred refresh command is:

```bash
bankcap write-mechanism-package \
  --panel data/derived/bankcap_analysis_panel.csv \
  --diagnostics-dir output/diagnostics \
  --report output/reports/h8_go_no_go_report.md \
  --memo output/reports/h8_mechanism_screen_memo.md \
  --summary output/reports/h8_mechanism_summary.json \
  --manifest output/reports/h8_mechanism_package_manifest.csv \
  --figures-dir output/figures
```

Validate the refreshed package with:

```bash
bankcap validate-mechanism-package \
  --manifest output/reports/h8_mechanism_package_manifest.csv
```

## Interpretation boundary

Use this package as descriptive mechanism evidence. H.8 bank groups do not identify individual
banks, merger-adjusted bank behavior, bank-level duration exposure, or causal absorption.

H.8 securities should be described as H.8 securities or Treasury-plus-agency context unless a source
mapping proves a narrower Treasury-only label. Call Report or FR Y-9C work should begin only after a
separate design memo explains why mixed H.8 stability is still worth the data cost.
