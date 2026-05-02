# Implementation plan

## Tranche 0: Seed verification

- Install package in editable mode.
- Run synthetic tests.
- Validate `config/project.yaml`.
- Confirm no raw data or generated outputs are committed.

## Tranche 1: Source-contract validation and local import

- Validate `buycurve`, `tdcladder`, and `liqsub` required outputs.
- Copy them into `data/imported/` with manifests.
- Inspect column names and units.
- Update aliases in `src/bankcap/h8.py` and `src/bankcap/treasury_context.py` only where necessary.

## Tranche 2: Real H.8 bank-group adapter

- Map imported H.8 outcomes into canonical long form.
- Confirm group labels: large domestic, small domestic, foreign-related.
- Decide monthly conversion: final weekly observation versus monthly mean; document choice.
- Build ratios and within-group changes.
- Validate against `config/schemas/h8_bank_group_outcomes.yaml`.

## Tranche 3: Treasury context

- Confirm `buycurve` bill share and gross issuance columns.
- Confirm `tdcladder` WAM and liquidity-weighted supply columns and units.
- Confirm `liqsub` TGA change and plumbing flags.
- Apply calendar and data-driven episode flags.
- Validate against `config/schemas/treasury_context.yaml`.

## Tranche 4: Analysis panel and diagnostics

- Merge H.8 and Treasury context on period.
- Run descriptive trends, bill-heavy/coupon-heavy response tables, correlations, guarded regressions,
  and event windows.
- Add figures only after tables are stable.
- Keep generated outputs under ignored `output/`.

## Tranche 5: Go/no-go report

- Write the H.8 go/no-go report.
- Decide whether there is enough evidence for a bank-level design memo.
- If yes, draft the Call Report / FR Y-9C memo before downloading new bank-level data.
- Status: complete. The current package is partial go for H.8 mechanism context only; bank-level
  ingestion remains blocked.

## Tranche 6: Optional comparison anchors

- Import `tdcest` or `tdcpass` only if the H.8 result needs quarterly TDC/pass-through comparison.
- Keep these anchors separate from the first-pass H.8 mechanism screen.
- Status: not needed for the completed H.8 mechanism package.
