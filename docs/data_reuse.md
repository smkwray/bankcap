# Data reuse plan

`bankcap` should be a downstream mechanism screen. It should not reproduce sibling transformations
unless a gap is documented.

## Required first-pass sources

### Federal Reserve H.8

Use the H.8 Data Download Program target-group packages for large domestically chartered banks, small
domestically chartered banks, and foreign-related institutions. These packages fill the target
bank-group gap that sibling outputs do not cover.

Guardrail: H.8 group aggregates are mechanism context, not bank-level identification. Securities are
Treasury-and-agency securities, not pure Treasury holdings.

### buycurve

Use for issuance composition, bill share, maturity buckets, buyer shares, and auction-to-holder H.8
context. Core artifacts are listed in `config/source_contracts/buycurve.yaml`.

Guardrail: auction allotments are initial absorption, not final holders. Dealer allotment is an
intermediation bridge.

### tdcladder

Use for WAM, bill share, liquidity-weighted Treasury supply, TDC comparison surfaces, and first-pass
episode designs. Core artifacts are listed in `config/source_contracts/tdcladder.yaml`.

Guardrail: liquidity weights are measurement assumptions, not structural facts.

### liqsub

Use for H.8/H.4.1/OFR plumbing panels, TGA/reserves/ON RRP/MMF context, evidence gates, and large TGA
rebuild diagnostics. Core artifacts are listed in `config/source_contracts/liqsub.yaml`.

Guardrail: broad substitution claims are blocked. Use this repository as plumbing context and for
evidence gates, not as headline causal evidence.

## Optional comparison anchors

`tdcest` and `tdcpass` are optional quarterly anchors. They should not be first-pass dependencies.
Use them only if the H.8 screen needs TDC/pass-through comparison context.

## Import boundary

Sibling outputs are copied into ignored paths under `data/imported/<sibling>/`. Generated bankcap
panels go under ignored `data/derived/`. Reports and diagnostics go under ignored `output/`.

This keeps the committed repository small and prevents raw data or generated bulk output from leaking
into the seed.
