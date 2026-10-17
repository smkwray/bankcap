# BankCap

BankCap compares Federal Reserve H.8 bank-group balance sheets with Treasury
issuance and funding conditions. It describes deposits, loans, securities, and
cash assets for large domestic banks, small domestic banks, and foreign-related
institutions. It provides aggregate context for the
[Treasury Deposit Component (TDC)](https://github.com/smkwray/tdcest).

The implemented analysis is an H.8 group-level screen. It does not ingest
individual-bank Call Reports or FR Y-9C filings, and it does not identify causal
Treasury absorption or bank-level differences in duration capacity.

## Install and validate

Python 3.11 or later is required. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,analysis]'
python -B -m pytest -q
ruff check .
bankcap validate-config
```

The `analysis` extra supplies plotting and statistical packages.

## Inputs and workflow

H.8 inputs come from the Federal Reserve Data Download Program. Treasury and
money-market context comes from
[BuyCurve](https://github.com/smkwray/buycurve),
[TDCLadder](https://github.com/smkwray/tdcladder), and
[LiqSub](https://github.com/smkwray/liqsub).
The [source contracts](config/source_contracts/) define the required exports.

1. Validate and copy the required sibling exports using
   `validate-sibling-sources` and `copy-sibling-outputs`.
2. Download H.8 packages with `download-h8-target-groups`, normalize them with
   `build-h8-target-input`, and run `build-h8-panel`.
3. Run `build-treasury-context` and `build-analysis-panel`.
4. Build and validate the diagnostic package:

```bash
bankcap write-mechanism-package
bankcap validate-mechanism-package
```

The [CLI reference](docs/cli_reference.md) gives complete commands and paths.
Run `bankcap --help` for options. Configuration and episode windows live in
`config/project.yaml` and `config/episodes.yaml`.

## Outputs and limits

The package writes descriptive contrasts, cutoff-sensitivity tables, event-window
summaries, figures, and a machine-readable summary. Fixed bill-heavy and
coupon-heavy categories can have unequal or empty support; relative bill-share
comparisons and support counts must accompany their interpretation. The
[H.8 analysis summary](docs/h8_mechanism_package.md) records the available
screen's coverage and mixed stability.

H.8 securities can combine Treasury and agency holdings. Group-level co-movement
does not identify an individual bank's purchases, funding source, regulatory
constraint, or causal response. See the
[claim boundaries](docs/claim_boundaries.md) and
[H.8 versus bank-level comparison](docs/h8_vs_bank_level_identification.md).

Raw data, imported sibling files, derived panels, reports, figures, and manifests
are generated locally under `data/` and `output/` and are ignored by Git. A fresh
clone includes source code, configuration, documentation, and synthetic tests.
