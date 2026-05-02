# bankcap

`bankcap` is the Project 5 workspace for the TDC thesis extension: **Bank-Level
Maturity Capacity, SLR, and Duration Constraints**. The first implementation is a
low-cost **Federal Reserve H.8 bank-group mechanism screen**, not a Call Report or
FR Y-9C bank-level project.

Core question:

> Which banks can absorb Treasury debt, and do their deposits, loans, funding,
> and liquidity buffers respond differently when Treasury financing is bill-heavy,
> coupon-heavy, or concentrated in TGA rebuild/QT/high-rate episodes?

## What this seed includes

```text
bankcap/
├── README.md
├── pyproject.toml
├── config/
│   ├── project.yaml
│   ├── episodes.yaml
│   ├── source_contracts/
│   │   ├── buycurve.yaml
│   │   ├── tdcladder.yaml
│   │   ├── liqsub.yaml
│   │   ├── tdcest.yaml
│   │   └── tdcpass.yaml
│   └── schemas/
│       ├── h8_bank_group_outcomes.yaml
│       ├── treasury_context.yaml
│       └── analysis_panel.yaml
├── src/bankcap/
│   ├── cli.py
│   ├── config.py
│   ├── contracts.py
│   ├── h8.py
│   ├── treasury_context.py
│   ├── panel.py
│   ├── diagnostics.py
│   ├── reporting.py
│   ├── schemas.py
│   └── episodes.py
├── tests/
│   ├── fixtures/                 # small synthetic CSVs only
│   └── test_*.py
├── docs/
│   ├── research_design.md
│   ├── data_reuse.md
│   ├── claim_boundaries.md
│   ├── h8_vs_bank_level_identification.md
│   ├── call_report_y9c_gate.md
│   ├── cli_reference.md
│   ├── schema_reference.md
│   ├── implementation_plan.md
└── do/                            # local-only planning, ignored by git
    └── IMPLEMENTATION_TRANCHES.md
```

The repository intentionally excludes raw data and generated bulk outputs. Local imports from sibling
projects are copied into ignored paths under `data/imported/`; derived panels and reports are written
under ignored `data/derived/` and `output/`.

## Install and test

```bash
python -m venv ~/venvs/bankcap
source ~/venvs/bankcap/bin/activate
python -m pip install -e '.[dev]'
python -B -m pytest -q
bankcap validate-config
```

## First-pass workflow

Set sibling roots in your shell or pass `--source-root` per command:

```bash
export BUYCURVE_ROOT=../buycurve
export TDCLADDER_ROOT=../tdcladder
export LIQSUB_ROOT=../liqsub
```

Validate and import the required sibling outputs:

```bash
bankcap validate-sibling-sources --sibling buycurve --source-root "$BUYCURVE_ROOT" --required-only
bankcap validate-sibling-sources --sibling tdcladder --source-root "$TDCLADDER_ROOT" --required-only
bankcap validate-sibling-sources --sibling liqsub --source-root "$LIQSUB_ROOT" --required-only

bankcap copy-sibling-outputs --sibling buycurve --source-root "$BUYCURVE_ROOT" --required-only --manifest data/imported/buycurve_manifest.csv
bankcap copy-sibling-outputs --sibling tdcladder --source-root "$TDCLADDER_ROOT" --required-only --manifest data/imported/tdcladder_manifest.csv
bankcap copy-sibling-outputs --sibling liqsub --source-root "$LIQSUB_ROOT" --required-only --manifest data/imported/liqsub_manifest.csv
```

Build the seed panels:

```bash
bankcap download-h8-target-groups \
  --overwrite \
  --manifest data/raw/h8_ddp/download_manifest.csv

bankcap build-h8-target-input \
  --input-dir data/raw/h8_ddp \
  --output data/imported/h8_fed/target_group_h8_monthly_sa.csv

bankcap build-h8-panel \
  --input data/imported/h8_fed/target_group_h8_monthly_sa.csv \
  --output data/derived/h8_bank_group_panel.csv \
  --frequency monthly

bankcap build-treasury-context \
  --buycurve data/imported/buycurve/monthly_issuance_maturity_panel.csv \
  --tdcladder data/imported/tdcladder/monthly_ladder_panel.csv \
  --liqsub data/imported/liqsub/monthly_liquidity_substitution_panel.csv \
  --output data/derived/treasury_context_panel.csv

bankcap build-analysis-panel \
  --h8 data/derived/h8_bank_group_panel.csv \
  --context data/derived/treasury_context_panel.csv \
  --output data/derived/bankcap_analysis_panel.csv

bankcap run-diagnostics \
  --panel data/derived/bankcap_analysis_panel.csv \
  --output-dir output/diagnostics

bankcap write-go-no-go-report \
  --panel data/derived/bankcap_analysis_panel.csv \
  --diagnostics-dir output/diagnostics \
  --output output/reports/h8_go_no_go_report.md

bankcap write-mechanism-memo \
  --panel data/derived/bankcap_analysis_panel.csv \
  --diagnostics-dir output/diagnostics \
  --output output/reports/h8_mechanism_screen_memo.md

bankcap write-mechanism-figures \
  --panel data/derived/bankcap_analysis_panel.csv \
  --diagnostics-dir output/diagnostics \
  --output-dir output/figures

# Equivalent post-panel bundle for diagnostics, report, memo, and figures:
bankcap write-mechanism-package \
  --panel data/derived/bankcap_analysis_panel.csv \
  --diagnostics-dir output/diagnostics \
  --report output/reports/h8_go_no_go_report.md \
  --memo output/reports/h8_mechanism_screen_memo.md \
  --manifest output/reports/h8_mechanism_package_manifest.csv \
  --figures-dir output/figures

bankcap validate-mechanism-package \
  --manifest output/reports/h8_mechanism_package_manifest.csv
```

The H.8 target-group workflow downloads Federal Reserve DDP packages into ignored `data/raw/`,
normalizes complete monthly rows into ignored `data/imported/h8_fed/`, and then builds the derived
panel.

The diagnostics preserve fixed bill-heavy/coupon-heavy flags, add relative high-bill/low-bill
bucket tables, write a cutoff-sensitivity table for nearby relative bill-share splits, and summarize
configured event-window contrasts. The relative buckets are the safer first-pass comparison when
fixed coupon-heavy months have little or no support.

`write-mechanism-package` also writes `h8_mechanism_package_manifest.csv`, an index of the package
inputs and outputs with claim-boundary notes. `validate-mechanism-package` checks that the indexed
artifacts exist, CSVs and SVGs are nonempty/parseable, claim-boundary notes are populated, and
report text keeps boundary language.

## Required claim boundary

- H.8 bank-group evidence is mechanism context, not bank-level identification.
- H.8 securities may combine Treasury and agency securities; labels must say so.
- Do not claim bank-level heterogeneity without bank-level data.
- Do not infer causal absorption from descriptive H.8 co-movement.
- Call Reports or FR Y-9C should be a second phase only if the H.8 screen is promising.
- Reuse `buycurve`, `tdcladder`, and `liqsub` outputs before downloading new data or duplicating
  transformations.

## Sibling reuse

- `buycurve`: issuance composition, bill share, maturity buckets, buyer shares, and H.8 context.
- `tdcladder`: WAM, bill share, liquidity-weighted Treasury supply, TDC comparison, and episode surfaces.
- `liqsub`: H.8/H.4.1/OFR plumbing panels, TGA/reserves/ON RRP/MMF context, and evidence gates.
- `tdcest` and `tdcpass`: optional quarterly comparison anchors only after the H.8 screen needs them.

See `docs/data_reuse.md` and `config/source_contracts/*.yaml` for source contracts and guardrails.
