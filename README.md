# BankCap

BankCap compares monthly balance-sheet data from the Federal Reserve's H.8 release (Assets and Liabilities of Commercial Banks in the United States) for large domestic banks, small domestic banks, and foreign-related institutions against US Treasury issuance composition and money-market conditions. It downloads H.8 packages, merges them with monthly Treasury-context CSVs into a bank-group panel, and writes contrast tables, event-window summaries, SVG charts, and Markdown and JSON reports.

## Data

- Federal Reserve H.8 Data Download Program: seasonally adjusted monthly bank-group totals for large domestic banks, small domestic banks, and foreign-related institutions covering Treasury and agency securities, loans and leases, cash assets, and deposits (in USD millions).
- Monthly CSV exports from three sibling repositories (paths configured under `config/source_contracts/`):
  - [buycurve](https://github.com/smkwray/buycurve): monthly Treasury gross issuance, bill share, and maturity mix.
  - [tdcladder](https://github.com/smkwray/tdcladder): monthly weighted average maturity, bill share, and liquidity-weighted Treasury supply.
  - [liqsub](https://github.com/smkwray/liqsub): monthly Treasury General Account changes, bank reserves, balances at the Federal Reserve's overnight reverse repurchase (ON RRP) facility, and aggregate bank balance sheets.

A real build needs all three checkouts; the test suite runs offline on synthetic fixtures. Source contracts also list optional quarterly exports from [tdcest](https://github.com/smkwray/tdcest), which measures the Treasury Deposit Component (TDC), the part of the change in deposits at US banks and credit unions that comes from Treasury payments and trades in Treasury securities, and from [tdcpass](https://github.com/smkwray/tdcpass). The validate and copy commands handle them, but the panel and reports do not use them. No API keys are required. Setting `BUYCURVE_ROOT`, `TDCLADDER_ROOT`, `LIQSUB_ROOT`, `TDCEST_ROOT`, or `TDCPASS_ROOT` lets `validate-sibling-sources` find a checkout without `--source-root`.

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

Validate the required sibling exports and copy them into `data/imported/`:

```bash
for s in buycurve tdcladder liqsub; do
  bankcap validate-sibling-sources --sibling $s --source-root ../$s --required-only
  bankcap copy-sibling-outputs --sibling $s --source-root ../$s --required-only
done
```

Download and normalize the H.8 bank-group packages, build the monthly Treasury context, and merge them into the analysis panel:

```bash
bankcap download-h8-target-groups --overwrite
bankcap build-h8-target-input
bankcap build-h8-panel --input data/imported/h8_fed/target_group_h8_monthly_sa.csv
bankcap build-treasury-context \
  --buycurve data/imported/buycurve/monthly_issuance_maturity_panel.csv \
  --tdcladder data/imported/tdcladder/monthly_ladder_panel.csv \
  --liqsub data/imported/liqsub/monthly_liquidity_substitution_panel.csv
bankcap build-analysis-panel
```

Write and check the outputs. `write-mechanism-package` runs the diagnostics on the analysis panel and writes the tables, charts, Markdown and JSON reports, and a file manifest; `validate-mechanism-package` checks that every file in the manifest exists and is well formed:

```bash
bankcap write-mechanism-package
bankcap validate-mechanism-package
```

Thresholds and calendar episode windows live in `config/project.yaml` and `config/episodes.yaml`. Run `bankcap --help` or see the [command reference](docs/cli_reference.md) for every command and option.

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

- The pipeline uses aggregate H.8 bank-group totals and does not ingest individual-bank Call Reports or the FR Y-9C financial statements of bank holding companies. Group-level co-movement does not identify individual-bank purchases, funding sources, regulatory constraints, or causal Treasury absorption.
- H.8 securities combine Treasury and agency securities.
- Fixed bill-heavy (>= 60% bill share) and coupon-heavy (<= 40% bill share) definitions in `config/project.yaml` can have thin or empty sample support; read them alongside the relative bill-share quantile contrasts and support counts.

## Tests

The test suite uses synthetic fixtures and runs offline:

```bash
python -B -m pytest -q
ruff check .
```

## License

MIT. See [LICENSE](LICENSE).
