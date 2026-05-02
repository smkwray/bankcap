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

The seed accepts long-form H.8-style data. The next implementation tranche should adapt real imported
H.8 columns into this canonical shape.

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
```
