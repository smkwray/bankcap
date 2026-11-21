# BankCap

BankCap compares monthly Federal Reserve H.8 balance-sheet data for large domestic banks, small domestic banks, and foreign-related institutions against US Treasury issuance composition and money-market conditions. It downloads H.8 packages, merges them with monthly Treasury-context CSVs into a bank-group panel, and writes contrast tables, event-window summaries, SVG charts, and Markdown and JSON reports.

## Data

- Federal Reserve H.8 Data Download Program: seasonally adjusted monthly bank-group totals for large domestic banks, small domestic banks, and foreign-related institutions covering Treasury and agency securities, loans and leases, cash assets, and deposits (in USD millions).
- Upstream monthly CSV inputs (paths configured under `config/source_contracts/`):
  - `buycurve`: monthly Treasury gross issuance, bill share, and maturity mix.
  - `tdcladder`: monthly weighted average maturity, bill share, and liquidity-weighted Treasury supply.
  - `liqsub`: monthly Treasury General Account changes, bank reserves, ON RRP, and aggregate bank balance sheets.

Optional quarterly comparison inputs from `tdcest` and `tdcpass` are also configured under `config/source_contracts/`. No API keys are required. Set `BUYCURVE_ROOT`, `TDCLADDER_ROOT`, `LIQSUB_ROOT`, `TDCEST_ROOT`, or `TDCPASS_ROOT` to point to sibling checkouts without passing `--source-root`.

## Install

Python 3.11 or later is required. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,analysis]'
```

The `analysis` extra installs `matplotlib` and `statsmodels`; `dev` installs `pytest` and `ruff`.

## Usage

Check configuration and schema paths:

```bash
bankcap validate-config
```

Validate and copy the required upstream monthly exports into `data/imported/`:

```bash
bankcap validate-sibling-sources --sibling buycurve --source-root ../buycurve --required-only
bankcap validate-sibling-sources --sibling tdcladder --source-root ../tdcladder --required-only
bankcap validate-sibling-sources --sibling liqsub --source-root ../liqsub --required-only

bankcap copy-sibling-outputs --sibling buycurve --source-root ../buycurve --required-only
bankcap copy-sibling-outputs --sibling tdcladder --source-root ../tdcladder --required-only
bankcap copy-sibling-outputs --sibling liqsub --source-root ../liqsub --required-only
```

Download the Federal Reserve H.8 bank-group packages, normalize them, and build the H.8 panel:

```bash
bankcap download-h8-target-groups --overwrite
bankcap build-h8-target-input
bankcap build-h8-panel --input data/imported/h8_fed/target_group_h8_monthly_sa.csv
```

Build the monthly Treasury context, merge it with the H.8 panel, and generate and check the full output package:

```bash
bankcap build-treasury-context \
  --buycurve data/imported/buycurve/monthly_issuance_maturity_panel.csv \
  --tdcladder data/imported/tdcladder/monthly_ladder_panel.csv \
  --liqsub data/imported/liqsub/monthly_liquidity_substitution_panel.csv

bankcap build-analysis-panel
bankcap write-mechanism-package
bankcap validate-mechanism-package
```

Thresholds and calendar episode windows live in `config/project.yaml` and `config/episodes.yaml`. Run `bankcap --help` or see `docs/cli_reference.md` for all commands and options.

## Output

All downloaded inputs, panels, tables, figures, and reports live under `data/` and `output/` and are ignored by Git.

| Path | Description |
| --- | --- |
| `data/derived/h8_bank_group_panel.csv` | Monthly H.8 levels, changes, and balance-sheet shares by bank group (USD millions and shares) |
| `data/derived/bankcap_analysis_panel.csv` | Merged monthly bank-group and Treasury-context panel |
| `output/diagnostics/` | CSV tables for sample coverage, bank-group trends, bill-share contrasts, correlations, regressions, and event windows |
| `output/reports/` | Summary Markdown reports, JSON summary, and file manifest |
| `output/figures/` | SVG trend and bill-share contrast charts |

## Limits

- The pipeline uses aggregate H.8 bank-group totals and does not ingest individual-bank Call Reports or FR Y-9C filings. Group-level co-movement does not identify individual-bank purchases, funding sources, regulatory constraints, or causal Treasury absorption.
- H.8 securities combine Treasury and agency securities.
- Fixed bill-heavy (>= 60% bill share) and coupon-heavy (<= 40% bill share) definitions in `config/project.yaml` can have thin or empty sample support; read them alongside the relative bill-share quantile contrasts and support counts.

## Tests

The test suite uses synthetic fixtures and runs offline:

```bash
python -B -m pytest -q
ruff check .
```
