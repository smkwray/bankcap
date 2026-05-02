# CLI reference

## Validate config

```bash
bankcap validate-config --config config/project.yaml
```

Checks project config, schema paths, source-contract paths, and claim-boundary presence.

## Validate sibling sources

```bash
bankcap validate-sibling-sources --sibling buycurve --source-root ../buycurve --required-only
bankcap validate-sibling-sources --sibling tdcladder --source-root ../tdcladder --required-only
bankcap validate-sibling-sources --sibling liqsub --source-root ../liqsub --required-only
```

Use `--strict-columns` for minimal CSV column checks. Use `--imported` to check `data/imported/`
after copying.

## Copy sibling outputs

```bash
bankcap copy-sibling-outputs --sibling buycurve --source-root ../buycurve --required-only --manifest data/imported/buycurve_manifest.csv
```

Copied files are ignored by git.

## Build H.8 panel

```bash
bankcap build-h8-panel --input <h8-long-form.csv> --output data/derived/h8_bank_group_panel.csv --frequency monthly
```

The builder accepts long-form H.8-style data with date, bank group, securities, deposits, loans, and
cash assets. It also accepts the normalized Federal Reserve H.8 target-group input produced below.

## Download and normalize H.8 target groups

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
```

The downloaded DDP packages and normalized local extract are ignored by git. The normalized H.8
extract keeps only complete rows for required H.8 levels.

The context builder preserves fixed bill-heavy/coupon-heavy flags and also writes relative
high-bill/low-bill quantile buckets. Use the relative buckets when fixed coupon-heavy support is too
thin for a stable comparison.

## Build Treasury context

```bash
bankcap build-treasury-context \
  --buycurve data/imported/buycurve/monthly_issuance_maturity_panel.csv \
  --tdcladder data/imported/tdcladder/monthly_ladder_panel.csv \
  --liqsub data/imported/liqsub/monthly_liquidity_substitution_panel.csv \
  --output data/derived/treasury_context_panel.csv
```

## Build analysis panel, diagnostics, report

```bash
bankcap build-analysis-panel
bankcap run-diagnostics
bankcap write-go-no-go-report
bankcap write-mechanism-memo
bankcap write-mechanism-figures
bankcap write-mechanism-package
bankcap validate-mechanism-package
```

`run-diagnostics` also writes `relative_bill_share_cutoff_sensitivity.csv`, a descriptive robustness
screen for nearby relative bill-share cutoffs, plus `event_window_summary.csv` and
`event_window_contrasts.csv` for configured policy/stress windows.

`write-mechanism-package` is a post-panel convenience wrapper. It reruns diagnostics and writes the
go/no-go report, mechanism memo, SVG figures, and a package manifest from the same panel.
`validate-mechanism-package` checks the manifest schema, artifact paths, claim-boundary notes, and
report boundary language.
